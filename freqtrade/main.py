#!/usr/bin/env python3
import copy
import json
import logging
import sys
import time
import traceback
from datetime import datetime
from typing import Dict, Optional, List

import requests
from cachetools import cached, TTLCache

from freqtrade import __version__, exchange, persistence, rpc, DependencyException, \
    OperationalException
from freqtrade.analyze import get_signal, SignalType
from freqtrade.misc import State, get_state, update_state, parse_args, throttle, \
    load_config
from freqtrade.persistence import Trade
from freqtrade.trade import handle_trade, calc_profit
from freqtrade.strategy import Strategy

logger = logging.getLogger('freqtrade')

_CONF = {}

EVENT_RPC = 1 # Send this event to RPC destinations (Telegram, etc..)

# this is supposed to turn off event logging, but it isn't
# accessable outside main.py (global doesnt work ?)
# either way it should be put into a 'env' object that we
# carry around.
_event_log = True # if True, send out and print events

def event_log(dst, what, msg):
    if _event_log:
        logger.info('%s, %s' %(what, msg))
        if (dst & EVENT_RPC) != 0:
            rpc.send_msg(msg)
    else:
        logger.info('####### not logging %s,  %s ######' %(what, msg))


def refresh_whitelist(strategy: Strategy, whitelist: Optional[List[str]] = None) -> None:
    """
    Check wallet health and remove pair from whitelist if necessary
    :param whitelist: a new whitelist (optional)
    :return: None
    """
    whitelist = whitelist or strategy.whitelist()

    sanitized_whitelist = []
    health = exchange.get_wallet_health()
    for status in health:
        pair = '{}_{}'.format(strategy.stake_currency(), status['Currency'])
        if pair not in whitelist:
            continue
        if status['IsActive']:
            sanitized_whitelist.append(pair)
        else:
            logger.info(
                'Ignoring %s from whitelist (reason: %s).',
                pair, status.get('Notice') or 'wallet is not active'
            )
    return sanitized_whitelist


def _process(strategy, dynamic_whitelist: Optional[int] = 0) -> bool:
    """
    Queries the persistence layer for open trades and handles them,
    otherwise a new trade is created.
    :param: dynamic_whitelist: True is a dynamic whitelist should be generated (optional)
    :return: True if a trade has been created or closed, False otherwise
    """
    state_changed = False
    try:
        # Refresh whitelist based on wallet maintenance
        sanitized_whitelist = refresh_whitelist(strategy,
            gen_pair_whitelist(strategy.stake_currency(), topn = dynamic_whitelist) if dynamic_whitelist else None
        )
        if strategy.whitelist() != sanitized_whitelist:
            logger.debug('Using refreshed pair whitelist: %s ...', sanitized_whitelist)
            strategy.set_whitelist(sanitized_whitelist)
        # Query trades from persistence layer
        trades = Trade.query.filter(Trade.is_open.is_(True)).all()
        if len(trades) < strategy.max_open_trades():
            try:
                # Create entity and execute trade
                state_changed = create_trade(strategy, strategy.stake_amount())
                if not state_changed:
                    logger.info(
                        'Checked all whitelisted currencies. '
                        'Found no suitable entry positions for buying. Will keep looking ...'
                    )
            except DependencyException as e:
                logger.warning('Unable to create trade: %s', e)

        for trade in trades:
            # Get order details for actual price per unit
            if trade.open_order_id:
                # Update trade with order values
                logger.info('Got open order for %s', trade)
                trade.update(exchange.get_order(trade.open_order_id))

            if trade.is_open and trade.open_order_id is None:
                # Check if we can sell our current pair
                trade_state = handle_trade(strategy, trade)
                if trade_state:
                    logger.info('    sell has triggered')
                    current_rate = exchange.get_ticker(trade.pair)['bid']
                    msg = execute_sell(trade, current_rate)
                    Trade.session.flush()
                    event_log(EVENT_RPC, 'execute_sell', msg)
                state_changed = trade_state or state_changed

            # FIX: do we really need to call flush here, even
            # though we do it in buy/sell?
            # Make a test that exposes that by remarking this
            # flush
            Trade.session.flush()
    except (requests.exceptions.RequestException, json.JSONDecodeError) as error:
        logger.warning(
            'Got %s in _process(), retrying in 30 seconds...',
            error
        )
        time.sleep(30)
    except OperationalException:
        rpc.send_msg('*Status:* Got OperationalException:\n```\n{traceback}```{hint}'.format(
            traceback=traceback.format_exc(),
            hint='Issue `/start` if you think it is safe to restart.'
        ))
        logger.exception('Got OperationalException. Stopping trader ...')
        update_state(State.STOPPED)
    return state_changed

def execute_sell(trade: Trade, limit: float) -> None:
    """
    Executes a limit sell for the given trade and limit
    :param trade: Trade instance
    :param limit: limit rate for the sell order
    :return: None
    """
    # Execute sell and update trade record
    order_id = exchange.sell(str(trade.pair), limit, trade.amount)
    # FIX: What if sell failed? TEST this, and also return None
    trade.open_order_id = order_id
    fmt_exp_profit = round(calc_profit(trade, limit) * 100, 2)
    msg = '*{}:* Selling [{}]({}) with limit `{:.8f} (profit: ~{:.2f}%)`'.format(
          trade.exchange,
          trade.pair.replace('_', '/'),
          exchange.get_pair_detail_url(trade.pair),
          limit,
          fmt_exp_profit)
    # FIX: dont return a message, let the caller handle it
    # FIX: the caller should also be responsible for calc_profit
    return msg

def create_trade(strategy: Strategy, stake_amount: float) -> bool:
    """
    Checks the implemented trading indicator(s) for a randomly picked pair,
    if one pair triggers the buy_signal a new trade record gets created
    :param stake_amount: amount of btc to spend
    :return: True if a trade object has been created and persisted, False otherwise
    """
    assert stake_amount
    assert strategy.stake_amount()
    assert strategy.stake_currency()
    logger.info(
        'Checking buy signals to create a new trade with stake_amount: %f ...',
        stake_amount
    )
    whitelist = copy.deepcopy(strategy.whitelist())
    # Check if stake_amount is fulfilled
    if exchange.get_balance(strategy.stake_currency()) < stake_amount:
        raise DependencyException(
            'stake amount is not fulfilled (currency={})'.format(strategy.stake_currency())
        )

    # Remove currently opened and latest pairs from whitelist
    for trade in Trade.query.filter(Trade.is_open.is_(True)).all():
        if trade.pair in whitelist:
            whitelist.remove(trade.pair)
            logger.debug('Ignoring %s in pair whitelist', trade.pair)
    if not whitelist:
        raise DependencyException('No pair in whitelist')

    # Pick pair based on StochRSI buy signals
    # FIX: whould we scramble whitelist before picking first feasible pair?
    for _pair in whitelist:
        if get_signal(strategy,_pair, SignalType.BUY):
            pair = _pair
            break
    else:
        return False

    # Calculate amount
    buy_limit = strategy.get_target_bid(exchange.get_ticker(pair))
    amount = stake_amount / buy_limit
    amount = round(amount,6)
    if(amount > 5):
        amount = round(amount,0)
    if(amount > 0.01):
        amount = round(amount,4)
    logger.info('Amount: %f' % amount)

    order_id = exchange.buy(pair, buy_limit, amount)
    # Create trade entity and return
    # FIX: move out the RPC messaging and let the return
    # value of this function signal wether and what we should RPC
    rpc.send_msg('*{}:* Buying [{}]({}) with limit `{:.8f}`'.format(
        exchange.get_name().upper(),
        pair.replace('_', '/'),
        exchange.get_pair_detail_url(pair),
        buy_limit
    ))
    # Fee is applied twice because we make a LIMIT_BUY and LIMIT_SELL
    trade = Trade(
        pair=pair,
        stake_amount=stake_amount,
        amount=amount,
        fee=exchange.get_fee() * 2,
        open_rate=buy_limit,
        open_date=datetime.utcnow(),
        exchange=exchange.get_name().upper(),
        open_order_id=order_id,
        # cant support this since strategy isn't persistent
        #strategy=strategy # A nice workaround, each trade could have a different Strategy 
    )
    Trade.session.add(trade)
    Trade.session.flush()
    return True


def init(config: dict, db_url: Optional[str] = None) -> None:
    """
    Initializes all modules and updates the config
    :param config: config as dict
    :param db_url: database connector string for sqlalchemy (Optional)
    :return: None
    """
    # Initialize all modules
    rpc.init(config)
    persistence.init(config, db_url)
    exchange.init(config)

    # Set initial application state
    initial_state = config.get('initial_state')
    if initial_state:
        update_state(State[initial_state.upper()])
    else:
        update_state(State.STOPPED)


@cached(TTLCache(maxsize=1, ttl=1800))
def gen_pair_whitelist(base_currency: str, topn: int = 20, key: str = 'BaseVolume') -> List[str]:
    """
    Updates the whitelist with with a dynamically generated list
    :param base_currency: base currency as str
    :param topn: maximum number of returned results, must be greater than 0
    :param key: sort key (defaults to 'BaseVolume')
    :return: List of pairs
    """
    summaries = sorted(
        (s for s in exchange.get_market_summaries() if s['MarketName'].startswith(base_currency)),
        key=lambda s: s.get(key) or 0.0,
        reverse=True
    )

    # topn must be greater than 0
    if not topn > 0:
        topn = 20

    return [s['MarketName'].replace('-', '_') for s in summaries[:topn]]


def cleanup() -> None:
    """
    Cleanup the application state und finish all pending tasks
    :return: None
    """
    rpc.send_msg('*Status:* `Stopping trader...`')
    logger.info('Stopping trader and cleaning up modules...')
    update_state(State.STOPPED)
    persistence.cleanup()
    rpc.cleanup()
    exit(0)


def main() -> None:
    """
    Loads and validates the config and handles the main loop
    :return: None
    """

    _event_log = True

    global _CONF
    args = parse_args(sys.argv[1:])
    if not args:
        exit(0)

    # Initialize logger
    logging.basicConfig(
        level=args.loglevel,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    logger.info(
        'Starting freqtrade %s (loglevel=%s)',
        __version__,
        logging.getLevelName(args.loglevel)
    )
    
    # Load and validate configuration
    _CONF = load_config(args.config)

    # Initialize all modules and start main loop
    if args.dynamic_whitelist:
        logger.info('Using dynamically generated whitelist. (--dynamic-whitelist detected)')

    # If the user ask for Dry run with a local DB instead of memory
    if args.dry_run_db:
        if _CONF.get('dry_run', False):
            _CONF.update({'dry_run_db': True})
            logger.info('Dry_run will use the DB file: "tradesv3.dry_run.sqlite". (--dry_run_db detected)')
        else:
            logger.info('Dry run is disabled. (--dry_run_db ignored)')

    strategy = Strategy(_CONF).load(args.strategy)
    logger.info('loaded strategy %s' % strategy.name())
    
    if not args.rekt:
        print('NOT going LIVE!\nThis is an untested friendly code-fork (for educational purposes only).\nLive-trading is disabled by default, to protect you from accidentially losing money.\nIF you know what you are doing add the "--rekt=yes" flag to go live.\n\nIF you want to live-trade you probably want to use the original code at: https://github.com/gcarq/freqtrade\n');
        sys.exit();

    try:
        init(_CONF)
        old_state = None
        while True:
            new_state = get_state()
            # Log state transition
            if new_state != old_state:
                rpc.send_msg('*Status:* `{}`'.format(new_state.name.lower()))
                logger.info('Changing state to: %s', new_state.name)

            if new_state == State.STOPPED:
                time.sleep(1)
            elif new_state == State.RUNNING:
                throttle(
                    _process,
                    min_secs=_CONF['internals'].get('process_throttle_secs', 10),
                    strategy=strategy,
                    dynamic_whitelist=args.dynamic_whitelist,
                )
            old_state = new_state
    except KeyboardInterrupt:
        logger.info('Got SIGINT, aborting ...')
    except BaseException:
        logger.exception('Got fatal exception!')
    finally:
        cleanup()

if __name__ == '__main__':
    main()


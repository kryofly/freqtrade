# pragma pylint: disable=missing-docstring,W0212

import math
import logging
from typing import Tuple, Dict

import json

import arrow
from pandas import DataFrame
from tabulate import tabulate

from freqtrade import exchange
from freqtrade.exchange import Bittrex
from freqtrade.trade import min_roi_reached
from freqtrade.misc import load_config, printdf
from freqtrade.optimize import load_data, preprocess
from freqtrade.persistence import Trade
from freqtrade.strategy import Strategy
from freqtrade.trade import calc_profit

logger = logging.getLogger(__name__)

def backtest_export_json(args, config, prepdata, results):
    logger.info('export to json file %s', args.export_json)
    tickint = str(args.ticker_interval)
    h = open(args.export_json, 'w')
    h.write('{"ticker_interval": %s,\n' % tickint)
    h.write('"pairs":[\n')
    i = 0
    for pair, pair_data in prepdata.items():
        if i > 0:
            h.write(',')
        i += 1
        h.write('"%s":{' % pair)
        pkeys = pair_data.keys()
        j = 0
        for key in pkeys:
            if j > 0:
                h.write(',')
            j += 1
            h.write('"%s":[' % key)
            val = pair_data[key]
            sorted = val.sort_index()
            k = 0
            date = False
            if key == 'date':
                date = True
            for col in sorted.index:
                if k > 0:
                    h.write(',')
                k += 1
                v = val[col]
                if date:
                    h.write('"%s"' % v)
                else:
                    if float(v):
                        if math.isnan(v):
                            h.write('null')
                        else:
                            h.write('%f' % v)
                    else:
                        h.write('"%s"' % v)
            h.write(']\n')
        h.write('}\n')
    h.write('],\n"results":\n')
    h.write(results.to_json())
    h.write('}\n')
    h.close()

def get_timeframe(data: Dict[str, Dict]) -> Tuple[arrow.Arrow, arrow.Arrow]:
    """
    Get the maximum timeframe for the given backtest data
    :param data: dictionary with backtesting data
    :return: tuple containing min_date, max_date
    """
    min_date, max_date = None, None
    for values in data.values():
        sorted_values = sorted(values, key=lambda d: arrow.get(d['T']))
        if not min_date or sorted_values[0]['T'] < min_date:
            min_date = sorted_values[0]['T']
        if not max_date or sorted_values[-1]['T'] > max_date:
            max_date = sorted_values[-1]['T']
    return arrow.get(min_date), arrow.get(max_date)


def generate_text_table(data: Dict[str, Dict], results: DataFrame, stake_currency, ticker_interval) -> str:
    """
    Generates and returns a text table for the given backtest data and the results dataframe
    :return: pretty printed table with tabulate as str
    """
    tabular_data = []
    headers = ['pair', 'buy count', 'avg profit', 'total profit', 'avg duration']
    for pair in data:
        result = results[results.currency == pair]
        tabular_data.append([
            pair,
            len(result.index),
            '{:.2f}%'.format(result.profit.mean() * 100.0),
            '{:.08f} {}'.format(result.profit.sum(), stake_currency),
            '{:.2f}'.format(result.duration.mean() * ticker_interval),
        ])

    # Append Total
    tabular_data.append([
        'TOTAL',
        len(results.index),
        '{:.2f}%'.format(results.profit.mean() * 100.0),
        '{:.08f} {}'.format(results.profit.sum(), stake_currency),
        '{:.2f}'.format(results.duration.mean() * ticker_interval),
    ])
    return tabulate(tabular_data, headers=headers)

def backtest(config: Dict, # FIX: backtest doesn't use config anymore
             strategy: Strategy,
             processed: Dict[str, DataFrame],
             max_open_trades: int = 0,
             realistic: bool = True) -> DataFrame:
    """
    Implements backtesting functionality
    :param config: config to use
    :param processed: a processed dictionary with format {pair, data}
    :param max_open_trades: maximum number of concurrent trades (default: 0, disabled)
    :param realistic: do we try to simulate realistic trades? (default: True)
    :return: DataFrame
    """
    print('############################################################')
    print('---- BEGIN BACKTESTING ----')
    trades = []
    trade_count_lock = {}
    exchange._API = Bittrex({'key': '', 'secret': ''})
    for pair, pair_data in processed.items():
        pair_data['buy'], pair_data['sell'] = 0, 0
        ticker = strategy.populate_sell_trend(strategy.populate_buy_trend(pair_data))
        # for each buy point
        lock_pair_until = None
        for row in ticker[ticker.buy == 1].itertuples(index=True):
            if realistic:
                if lock_pair_until is not None and row.Index <= lock_pair_until:
                    continue
            if max_open_trades > 0:
                # Check if max_open_trades has already been reached for the given date
                if not trade_count_lock.get(row.date, 0) < max_open_trades:
                    continue

            if max_open_trades > 0:
                # Increase lock
                trade_count_lock[row.date] = trade_count_lock.get(row.date, 0) + 1
            trade = Trade(
                open_rate=row.close,
                open_date=row.date,
                amount = strategy.stake_amount(),
                fee=exchange.get_fee() * 2
            )
            # FIX: we aren't persistence with at_stoploss_glide_rate, need to call trade.session.flush here to save the updated val
            print('*** BUY %s date=%s, close=%s, amount=%s, fee=%s' %
                  (pair, row.date, row.close, trade.amount, trade.fee))

            # calculate win/lose forwards from buy point
            for row2 in ticker[row.Index + 1:].itertuples(index=True):
                strategy.step_frame(trade, row2.close, row2.date)
                trade.update_stats(row2.close)
                if max_open_trades > 0:
                    # Increase trade_count_lock for every iteration
                    trade_count_lock[row2.date] = trade_count_lock.get(row2.date, 0) + 1

                if min_roi_reached(strategy, trade, row2.close, row2.date) or row2.sell == 1:
                    current_profit = calc_profit(trade, row2.close)
                    lock_pair_until = row2.Index
                    print('*** SELL %s, date=%s min_roi_reached, close=%s profit=%s, duration=%s frames'
                          %(pair, row2.date, row2.close, current_profit, row2.Index - row.Index))

                    # FIX: add buy,sell date to the trade-log (row.date, row2.date)
                    trades.append((pair, current_profit, row2.Index - row.Index))
                    break
    print('---- trades: ----')
    print('1 frame consist of %d minutes' % strategy.tick_interval())
    print('columns: SYMBOL, profit(%, or BTC?), trade duration in frames')
    for tr in trades:
      print('trade:', tr)
    print('-----------------')
    labels = ['currency', 'profit', 'duration'] # FIX: add buy,sell dates here too
    print('### END BACKTESTING #########################################################')
    return DataFrame.from_records(trades, columns=labels)


def start(args):
    # Initialize logger
    logging.basicConfig(
        level=args.loglevel,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    print('---- backtesting start ----')
    exchange._API = Bittrex({'key': '', 'secret': ''})

    logger.info('Using config: %s ...', args.config)
    config = load_config(args.config)

    logger.info('Using ticker_interval: %s ...', args.ticker_interval)
    
    logger.info('loading strategy, file: %s' % args.strategy)
    strategy = Strategy().load(args.strategy)
    logger.info('loaded strategy %s' % strategy.name())

    data = {}
    pairs = config['exchange']['pair_whitelist']
    if pairs == []: # if there was an empty pairs_whitelist in config
        pairs = strategy.backtest_pairs()
    if args.live:
        logger.info('Downloading data for all pairs in whitelist ...')
        for pair in pairs:
            data[pair] = exchange.get_ticker_history(pair, args.ticker_interval)
    else:
        logger.info('Using local backtesting data, pairs: %s' % pairs)
        data = load_data(args.ticker_interval, pairs)

    amount = config['stake_amount']
    if amount == 0:
        amount = strategy.stake_amount()
    currency = config['stake_currency']
    if currency == None:
        currency = strategy.stake_currency()
    logger.info('Using stake_currency: %s ...', currency)
    logger.info('Using stake_amount: %s ...', amount)

    # Print timeframe
    min_date, max_date = get_timeframe(data)
    logger.info('Measuring data from %s up to %s ...', min_date.isoformat(), max_date.isoformat())

    max_open_trades = 0
    if args.realistic_simulation:
        max_open_trades = config['max_open_trades'] # FIX: remove from config
    else:
        max_open_trades = strategy.max_open_trades()
    logger.info('Using max_open_trades: %s ...', max_open_trades)

    # Monkey patch config
    from freqtrade import main
    main._CONF = config # FIX: remove this

    # Execute backtest and print results
    prepdata = preprocess(strategy, data)
    results = backtest(config, strategy,
                       prepdata, max_open_trades,
                       args.realistic_simulation)
    printdf(prepdata)
    logger.info(
        '\n====================== BACKTESTING REPORT ======================================\n%s',
        generate_text_table(data, results, config['stake_currency'], args.ticker_interval)
    )

    if args.export_json:
        backtest_export_json(args, config, prepdata, results)

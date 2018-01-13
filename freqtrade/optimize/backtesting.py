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
from freqtrade.misc import printdf
from freqtrade.optimize import load_data, preprocess
from freqtrade.persistence import Trade
from freqtrade.strategy import Strategy
from freqtrade.trade import calc_profit
from freqtrade.dataframe import file_write_dataframe_json
import freqtrade.misc as misc
from freqtrade import optimize

logger = logging.getLogger(__name__)

# Dont overuse this function, NaN is often a perfectly fine number
def zero_nan(num):
    if math.isnan(num):
        return 0
    else:
        return num

def backtest_export_json(args, config, prepdata, results):
    tickint = str(args.ticker_interval)
    h = open('backtest-result.json', 'w')
    h.write('{"ticker_interval": %s,\n' % tickint)
    h.write('"pairs":{\n')
    i = 0
    for pair, pair_data in prepdata.items():
        if i > 0:
            h.write(',')
        i += 1
        h.write('"%s":' % pair)
        file_write_dataframe_json(pair_data, h)
    h.write('},\n"results":\n')
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

def minutes_to_text(minutes):
    if minutes > 59:
        hours = int(minutes / 60)
        minutes -= hours * 60
        if hours > 23:
            days  = int(hours / 24)
            hours -= days * 24
            return '%dd%dh%dm' %(days, hours, minutes)
        else:
            return '%dh%dm' %(hours, minutes)
    return '%dm' % minutes

def generate_text_table(data: Dict[str, Dict], results: DataFrame, ticker_interval) -> str:
    """
    Generates and returns a text table for the given backtest data and the results dataframe
    :return: pretty printed table with tabulate as str
    """
    tabular_data = []
    headers = ['pair', 'buy count', 'avg profit', 'total profit', 'sharpe', 'drawdown', 'avg duration']
    tot_drawdown = 0 # FIX: could do some panda magick to avoid this
    for pair in data:
        result = results[results.currency == pair]
        if len(result.index) > 0: # skip pairs where we've made no trades
            v = result.profit.values
            std = v.std()
            if len(result.index) < 20: # StdDev when N is low is useless
                std = 1
            tot_drawdown += v.min()
            sharpe = v.mean() / std # express the average return in units of risk
                                    # assume we live in a zero-interest world
            duration_mean = zero_nan(result.duration.mean())
            tabular_data.append([
                pair,
                len(result.index),
                '{:.2f}%'.format(result.profit.mean() * 100.0),
                '{:.2f}%'.format(result.profit.sum()),
                '{:.2f}%'.format(sharpe),
                '{:.2f}%'.format(v.min()), # max Drawdown
                minutes_to_text(duration_mean * ticker_interval)
            ])
    # Append Total
    duration_mean = zero_nan(results.duration.mean())
    tabular_data.append([
        'TOTAL',
        len(results.index),
        '{:.2f}%'.format(results.profit.mean() * 100.0),
        '{:.2f}%'.format(results.profit.sum()),
        '{:.2f}%'.format(results.profit.mean() / results.profit.std()),
        '{:.2f}%'.format(tot_drawdown), # sum over min of each profit array in results
        minutes_to_text(duration_mean * ticker_interval)
    ])
    return tabulate(tabular_data, headers=headers)

def backtest_report_cost_average(prepdata):
    spent = 0 # track of how much base currency we spend
    sold  = 0 # track of how much base currency we sell
    for pair, pair_data in prepdata.items():
        closes = pair_data['close']
        ema_close = closes[0]
        vol = 0
        for close in closes:
            # buy 10 worth of base
            buyvol = 10 / close # the volume to spend 10 worth of base
            spent += (close * buyvol)
            vol += buyvol # track buyvolume
            ema_close = ema_close * 0.9 + close * 0.1
        sold += vol * ema_close
    return round(sold / spent, 2) # return profit ratio

def backtest(args) -> DataFrame:
    strategy = args['strategy']
    processed = args['processed']
    realistic = args.get('realistic', True)
    record = args.get('record', False)

    records = []
    trades = []
    #exchange._API = Bittrex({'key': '', 'secret': ''})
    for pair, pair_data in processed.items():
        pair_data['buy'], pair_data['sell'] = 0, 0
        ticker = strategy.populate_sell_trend(strategy.populate_buy_trend(pair_data))
        df = ticker
        # for each buy point
        lock_pair_until = None
        trade = Trade(open_rate=0,
                      open_date='',
                      amount = strategy.stake_amount(),
                      fee = strategy.fee() * 2
                     )
        tr = None
        # FIX: reintroduce max_open_trades count and realistic flag
        # strategy.max_open_trades
        for row in df.itertuples():
            if row.buy == 1 and tr == None:
                tr = (row.date, row.close, row.Index)
                trade.stat_max_rate = row.close
                trade.stat_min_rate = row.close
                trade.stat_stoploss_glide_rate = row.close
                trade.open_rate = row.close
                trade.open_date = row.date
                trade.amount = strategy.stake_amount(), # FIX: adjust amount towards buy_limit, just as we do in exchange trading
                trade.fee = strategy.fee() * 2
                #logger.info('*** BUY %s date=%s, close=%s, amount=%s, fee=%s' %
                #             (pair, row.date, row.close, trade.amount, trade.fee))
            if tr: # currently holding a trade
                strategy.step_frame(trade, row.close, row.date)
                trade.update_stats(row.close)
                #logger.info('update trade, buy_rate=%f, now_rate=%f, max=%f', trade.open_rate, row.close, trade.stat_max_rate)
                if min_roi_reached(strategy, trade, row.close, row.date) or row.sell == 1:
                    (o_date, o_close, o_index) = tr
                    current_profit = calc_profit(trade, row.close)
                    trades.append((pair, o_date, row.date, current_profit, row.Index - o_index))
                    reason = 'min_roi/stoploss'
                    if row.sell == 1:
                        reason = 'sell signal'
                    #logger.info('*** SELL %s, date=%s [%s], close=%s profit=%s, duration=%s frames'
                    #      %(pair, row.date, reason, row.close, current_profit, row.Index - o_index))
                    if record:
                        # Note, need to be json.dump friendly
                        # record a tuple of pair, current_profit_percent, entry-date, duration
                        print(o_date, o_close)
                        records.append((pair,
                                        current_profit,
                                        o_date.strftime('%s'),
                                        row.date.strftime('%s'),
                                        o_index,
                                        row.Index,
                                        ))

                    tr = None

    if record:
        logger.info('Dumping backtest trades')
        misc.file_dump_json('backtest-trades.json', records)

    #logger.info('---- trades: ----')
    #logger.info('1 frame consist of %d minutes' % strategy.tick_interval())
    #logger.info('columns: SYMBOL, profit(%, or BTC?), trade duration in frames')
    #for tr in trades:
    #  logger.info('trade: %s' % [tr])
    #logger.info('-----------------')
    #logger.info('### END BACKTESTING #########################################################')
    labels = ['currency', 'date_b', 'date_s', 'profit', 'duration'] # FIX: add buy,sell dates here too
    return DataFrame.from_records(trades, columns=labels)


def start(args):
    # Initialize logger
    logging.basicConfig(
        level=args.loglevel,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    logger.info('---- backtesting start ----')
    #exchange._API = Bittrex({'key': '', 'secret': ''})

    logger.info('Using config: %s ...', args.config)
    config = misc.load_config(args.config)

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
        data = load_data(args.datadir, args.ticker_interval, pairs)

    amount   = strategy.stake_amount()
    currency = strategy.stake_currency()
    logger.info('Using stake_currency: %s ...', currency)
    logger.info('Using stake_amount: %s ...', amount)

    # Print timeframe
    min_date, max_date = get_timeframe(data)
    logger.info('Measuring data from %s up to %s ...', min_date.isoformat(), max_date.isoformat())

    # --realistic-simulation shouldn't effect concurrently
    # open trades, because that is part of a strategy
    # (back-off strategy, etc)
    # but we should simulate slippage

    # Monkey patch config
    from freqtrade import main
    main._CONF = config # FIX: remove this

    record = False
    if args.export and args.export.find('trades') >= 0:
        record = True

    # Execute backtest and print results
    timeperiod=args.timeperiod
    if timeperiod:
        data = optimize.trim_tickerlist(data, timeperiod)
    prepdata = preprocess(strategy, data)
    results = backtest({'strategy': strategy,
                        'processed': prepdata,
                        'realistic': args.realistic_simulation,
                        'record': record
                       })

    printdf(prepdata)
    logger.info(
        '\n====================== BACKTESTING REPORT ======================================\n%s',
        generate_text_table(data, results, args.ticker_interval)
    )
    logger.info('Dollar-Cost-Average profit: %fx' % backtest_report_cost_average(prepdata))

    if args.export and args.export.find('result') >= 0:
        backtest_export_json(args, config, prepdata, results)

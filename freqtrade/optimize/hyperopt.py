# pragma pylint: disable=missing-docstring,W0212


import json
import logging
import sys
import math
from functools import reduce
from math import exp
from operator import itemgetter

from hyperopt import fmin, tpe, hp, Trials, STATUS_OK
from hyperopt.mongoexp import MongoTrials
from pandas import DataFrame

from freqtrade import exchange, optimize
from freqtrade.exchange import Bittrex
from freqtrade.optimize.backtesting import backtest
from freqtrade.vendor.qtpylib.indicators import crossed_above
from freqtrade.strategy import Strategy

# Remove noisy log messages
logging.getLogger('hyperopt.mongoexp').setLevel(logging.WARNING)
logging.getLogger('hyperopt.tpe').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# set TARGET_TRADES to suit your number concurrent trades so its realistic to 20days of data
TARGET_TRADES = 1100
TOTAL_TRIES = None
_CURRENT_TRIES = 0

TOTAL_PROFIT_TO_BEAT = 3
AVG_PROFIT_TO_BEAT = 0.2
AVG_DURATION_TO_BEAT = 50

# Configuration and data used by hyperopt
PROCESSED = None
STRATEGY = None

# Monkey patch config
from freqtrade import main
main._CONF = {} # clear it, so we are safe not to use main config, ie avoid going live for some bug/reason

def log_results(results):
    "if results is better than _TO_BEAT show it"

    current_try = results['current_tries']
    total_tries = results['total_tries']
    result = results['result']
    profit = results['total_profit'] / 1000

    outcome = '{:5d}/{}: {}'.format(current_try, total_tries, result)

    if profit >= TOTAL_PROFIT_TO_BEAT:
        logger.info(outcome)
    else:
        print('.', end='')
        sys.stdout.flush()

def optimizer(params):
    global _CURRENT_TRIES

    from freqtrade.optimize import backtesting
    STRATEGY.set_hyper_params(params)

    results = backtest({}, STRATEGY, PROCESSED)

    result = format_results(results)

    total_profit = results.profit.sum() * 1000
    if math.isnan(total_profit):
        total_profit = 0
    trade_count = len(results.index)

    trade_loss = 1 - 0.35 * exp(-(trade_count - TARGET_TRADES) ** 2 / 10 ** 5.2)
    profit_loss = max(0, 1 - total_profit / 10000)  # max profit 10000

    _CURRENT_TRIES += 1

    result_data = {
        'trade_count': trade_count,
        'total_profit': total_profit,
        'trade_loss': trade_loss,
        'profit_loss': profit_loss,
        'avg_profit': results.profit.mean() * 100.0,
        'avg_duration': results.duration.mean() * 5,
        'current_tries': _CURRENT_TRIES,
        'total_tries': TOTAL_TRIES,
        'result': result,
        'results': results
        }
    
    # logger.info('{:5d}/{}: {}'.format(_CURRENT_TRIES, TOTAL_TRIES, result))
    log_results(result_data)

    return {
        'loss': trade_loss + profit_loss,
        'status': STATUS_OK,
        'result': result
    }


def format_results(results: DataFrame):
    return ('Made {:6d} buys. Average profit {: 5.2f}%. '
            'Total profit was {: 7.3f}. Average duration {:5.1f} mins.').format(
                len(results.index),
                results.profit.mean() * 100.0,
                results.profit.sum(),
                results.duration.mean() * 5,
            )

def start(args):
    global TOTAL_TRIES
    global PROCESSED
    global STRATEGY

    TOTAL_TRIES = args.epochs

    exchange._API = Bittrex({'key': '', 'secret': ''})

    # Initialize logger
    logging.basicConfig(
        level=args.loglevel,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    if args.mongodb:
        logger.info('Using mongodb ...')
        logger.info('Start scripts/start-mongodb.sh and start-hyperopt-worker.sh manually!')

        db_name = 'freqtrade_hyperopt'
        trials = MongoTrials('mongo://127.0.0.1:1234/{}/jobs'.format(db_name), exp_key='exp1')
    else:
        trials = Trials()

    logger.info('loading strategy, file: %s' % args.strategy)
    strategy = Strategy()
    strategy.load(args.strategy)
    logger.info('loaded strategy %s' % strategy.name())
    STRATEGY = strategy

    # load raw tick data from disk
    dfs = optimize.load_data(strategy.tick_interval(),
                             strategy.backtest_pairs())
    # preprocess it by adding INDicators/OSCillators and
    # also BUY/SELL trigger-vectors
    PROCESSED = optimize.preprocess(strategy, dfs)

    best = fmin(fn=optimizer, space=strategy.buy_strategy_space(), algo=tpe.suggest, max_evals=TOTAL_TRIES, trials=trials)
    logger.info('Best parameters:\n%s', json.dumps(best, indent=4))
    results = sorted(trials.results, key=itemgetter('loss'))
    logger.info('Best Result:\n%s', results[0]['result'])

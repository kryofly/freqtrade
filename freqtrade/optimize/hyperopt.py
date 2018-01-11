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


# use --target_trades=x to suit your number concurrent trades so its realistic to 20days of data

TOTAL_PROFIT_TO_BEAT = 3
AVG_PROFIT_TO_BEAT = 0.2
AVG_DURATION_TO_BEAT = 50

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

def optimizer(params, args):
    strategy = args['strategy']

    from freqtrade.optimize import backtesting
    strategy.set_hyper_params(params)

    results = backtest(strategy, args['processed'])

    result = format_results(results)

    total_profit = results.profit.sum() * 1000
    if math.isnan(total_profit):
        total_profit = 0
    trade_count = len(results.index)
    target_trades = args['target_trades']
    trade_loss = 1 - 0.35 * exp(-(trade_count - target_trades) ** 2 / 10 ** 5.2)
    profit_loss = max(0, 1 - total_profit / 10000)  # max profit 10000

    args['current_tries'] += 1

    result_data = {
        'trade_count': trade_count,
        'total_profit': total_profit,
        'trade_loss': trade_loss,
        'profit_loss': profit_loss,
        'avg_profit': results.profit.mean() * 100.0,
        'avg_duration': results.duration.mean() * 5,
        'current_tries': args['current_tries'],
        'total_tries': args['epochs'], #TOTAL_TRIES,
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
    strategy = Strategy().load(args.strategy)
    logger.info('loaded strategy %s' % strategy.name())

    # load raw tick data from disk
    dfs = optimize.load_data(args.datadir,
                             strategy.tick_interval(),
                             strategy.backtest_pairs())
    # preprocess it by adding INDicators/OSCillators and
    # also BUY/SELL trigger-vectors
    prepdata = optimize.preprocess(strategy, dfs)

    optargs = {'epochs': args.epochs,
               'target_trades': args.target_trades,
               'current_tries': 0,
               'strategy': strategy,
               'processed': prepdata
              }
    fun = lambda params: optimizer(params, optargs)

    best = fmin(fn=fun, space=strategy.strategy_space(), algo=tpe.suggest, max_evals=args.epochs, trials=trials)
    logger.info('Best parameters:\n%s', json.dumps(best, indent=4))
    results = sorted(trials.results, key=itemgetter('loss'))
    logger.info('Best Result:\n%s', results[0]['result'])

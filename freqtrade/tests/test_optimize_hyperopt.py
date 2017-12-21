# pragma pylint: disable=missing-docstring,W0212

import random

from unittest.mock import MagicMock

from freqtrade.strategy import Strategy
from freqtrade import optimize
from freqtrade.optimize.hyperopt import start, optimizer

def setup_strategy():
    s = Strategy()
    s.set_backtest_pairs(['BTC_UNITEST'])
    return s

def fiftyfifty():
    random.random() > 0.5

# KLUDGY: we rely on the default strategy space and
#         make a pick from it
def gen_hyper_params():
    return {'adx':   {'enabled': fiftyfifty(), 'value': 38.0},
            'fastd': {'enabled': fiftyfifty(), 'value': 25.0},
            'green_candle': {'enabled': fiftyfifty()},
            'mfi':      {'enabled': fiftyfifty()},
            'over_sar': {'enabled': fiftyfifty()},
            'rsi':      {'enabled': fiftyfifty(), 'value': 33.0},
            'uptrend_long_ema': {'enabled':  fiftyfifty()},
            'uptrend_short_ema': {'enabled': fiftyfifty()},
            'uptrend_sma': {'enabled': fiftyfifty()},
            'trigger': {'type': 'lower_bb'}
           }

def test_optimizer_start():
    strategy = setup_strategy()
    args = MagicMock()
    args.epochs = 1
    args.mongodb = False
    args.strategy = None
    args.target_trades = 10
    args.datadir = 'freqtrade/tests/testdata'
    start(args)

def test_optimizer():
    strategy = setup_strategy()
    dfs = optimize.load_data('freqtrade/tests/testdata', 1, strategy.backtest_pairs())
    prepdata = optimize.preprocess(strategy, dfs)
    optargs = {'epochs': 1,
               'target_trades': 10,
               'current_tries': 0,
               'strategy': strategy,
               'processed': prepdata
              }
    params = gen_hyper_params()
    result = optimizer(params, optargs)
    assert result['loss']
    assert result['result']
    assert result['status']

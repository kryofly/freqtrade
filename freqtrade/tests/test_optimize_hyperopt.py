# pragma pylint: disable=missing-docstring,W0212

import random

import hyperopt.pyll.stochastic
from unittest.mock import MagicMock

from freqtrade.strategy import Strategy
from freqtrade import optimize
from freqtrade.optimize.hyperopt import start, optimizer

def setup_strategy():
    s = Strategy()
    s.set_backtest_pairs(['BTC_UNITEST'])
    return s

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
    space  = strategy.strategy_space()
    sample = hyperopt.pyll.stochastic.sample(space)
    result = optimizer(sample, optargs)
    assert result['loss']
    assert result['result']
    assert result['status']

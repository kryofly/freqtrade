# pragma pylint: disable=missing-docstring,W0212

from unittest.mock import MagicMock

from freqtrade.strategy import Strategy
#from freqtrade import optimize
from freqtrade.optimize.hyperopt import start

def setup_strategy():
    s = Strategy()
    s.set_backtest_pairs(['BTC_UNITEST'])
    return s

def test_optimizer(default_conf, mocker):
    strategy = setup_strategy()
    args = MagicMock()
    args.epochs = 1
    args.mongodb = False
    args.strategy = None
    args.target_trades = 10
    x = start(args)


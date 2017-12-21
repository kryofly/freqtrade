# pragma pylint: disable=missing-docstring,W0212

import pytest
import math

from freqtrade import optimize
from freqtrade.optimize.backtesting import backtest
from freqtrade.strategy import Strategy

def setup_strategy():
    s = Strategy()
    #s.set_backtest_pairs(['BTC_ETH', 'BTC_UNITEST'])
    return s

def load_data_test(what):
    data = optimize.load_data(ticker_interval=1, pairs=['BTC_UNITEST'])
    pair = data['BTC_UNITEST']
    # Depending on the what parameter we now adjust the
    # loaded data:
    # pair :: [{'O': 0.123, 'H': 0.123, 'L': 0.123, 'C': 0.123, 'V': 123.123, 'T': '2017-11-04T23:02:00', 'BV': 0.123}]
    if what == 'raise':
        o = h = l = c = 0.001
        l -= 0.0001
        h += 0.0001
        for frame in pair:
            o += 0.0001
            h += 0.0001
            l += 0.0001
            c += 0.0001
            o = round(o,9) # round to satoshis
            h = round(h,9)
            l = round(l,9)
            c = round(c,9)
            frame['O'] = o
            frame['H'] = h
            frame['L'] = l
            frame['C'] = c
    if what == 'lower':
        o = h = l = c = 0.001
        l -= 0.0001
        h += 0.0001
        for frame in pair:
            o -= 0.0001
            h -= 0.0001
            l -= 0.0001
            c -= 0.0001
            o = round(o,9) # round to satoshis
            h = round(h,9)
            l = round(l,9)
            c = round(c,9)
            frame['O'] = o
            frame['H'] = h
            frame['L'] = l
            frame['C'] = c
    if what == 'sine':
        i = 0
        o = h = l = c = (2 + math.sin(i/10)) / 1000
        h += 0.0001
        l -= 0.0001
        for frame in pair:
            o = (2 + math.sin(i/10)) / 1000 
            h = (2 + math.sin(i/10)) / 1000 + 0.0001
            l = (2 + math.sin(i/10)) / 1000 - 0.0001
            c = (2 + math.sin(i/10)) / 1000 - 0.000001

            o = round(o,9) # round to satoshis
            h = round(h,9)
            l = round(l,9)
            c = round(c,9)
            frame['O'] = o
            frame['H'] = h
            frame['L'] = l
            frame['C'] = c
            i += 1
    return data

# Test backtest on offline data
# loaded by freqdata/optimize/__init__.py::load_data()

def test_backtest(default_conf):
    strategy = setup_strategy()

    data = optimize.load_data(ticker_interval=5, pairs=['BTC_ETH'])
    print('Strategy: ', strategy)
    results = backtest(strategy, optimize.preprocess(strategy, data), 10, True)
    num_resutls = len(results)
    assert num_resutls > 0


def test_1min_ticker_interval(default_conf):
    strategy = setup_strategy()

    # Run a backtesting for an exiting 5min ticker_interval
    data = optimize.load_data(ticker_interval=1, pairs=['BTC_UNITEST'])
    results = backtest(strategy, optimize.preprocess(strategy, data), 1, True)
    assert len(results) > 0

    # Run a backtesting for 5min ticker_interval
    with pytest.raises(FileNotFoundError):
        data = optimize.load_data(ticker_interval=5, pairs=['BTC_UNITEST'])
        results = backtest(strategy, optimize.preprocess(strategy, data), 1, True)

def test_processed(default_conf):
    strategy = setup_strategy()
    data = load_data_test('raise')
    processed = optimize.preprocess(strategy, data)

def simple_backtest(config, strategy, contour, num_results):
    data = load_data_test(contour)
    processed = optimize.preprocess(strategy, data)
    assert isinstance(processed, dict)
    results = backtest(strategy, processed, 1, True)
    # results :: <class 'pandas.core.frame.DataFrame'>
    if num_results == 0:
        assert len(results) == 0
    else:
        assert num_results(results)

def test_raise(default_conf):
    strategy = setup_strategy()
    tests = [['raise', 0], ['lower', 0], ['sine', lambda x: len(x) > 0]]
    for [contour, numres] in tests:
        simple_backtest(default_conf, strategy, contour, numres)

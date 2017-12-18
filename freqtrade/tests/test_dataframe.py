# pragma pylint: disable=missing-docstring,W0621

import pytest
import pandas

from freqtrade import analyze
from freqtrade import dataframe
from freqtrade.strategy import Strategy
from freqtrade.dataframe import load_dataframe
from pandas import DataFrame

_pairs = ['BTC_ETH']

def _load_dataframe_pair(pairs):
    strategy = Strategy()
    ld = load_dataframe(ticker_interval=5, pairs=pairs)
    dataframe = ld[pairs[0]]
    dataframe = analyze.analyze_ticker(strategy,dataframe)
    return dataframe

@pytest.fixture
def result():
    return 0

def test_dataframe_load(result):
    dataframe = _load_dataframe_pair(_pairs)
    assert isinstance(dataframe, pandas.core.frame.DataFrame)

def test_dataframe_columns_exists(result):
    strategy = Strategy()
    dataframe = _load_dataframe_pair(_pairs)
    assert 'high'  in dataframe.columns
    assert 'low'   in dataframe.columns
    assert 'close' in dataframe.columns


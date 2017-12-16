# pragma pylint: disable=missing-docstring,W0621

import pytest

from freqtrade import analyze
from freqtrade import dataframe

@pytest.fixture
def result():
    return 0

def test_dataframe_columns_exists(result):
    dataframes = analyze.analyze_ticker(['BTC_ETH'])
    dataframe = dataframes['BTC_ETH']
    assert 'close' in dataframe.columns


# pragma pylint: disable=missing-docstring

import json
import os
from typing import Optional, List, Dict

from pandas import DataFrame

from freqtrade.analyze import populate_indicators, parse_ticker_dataframe
from freqtrade.strategy import Strategy

def load_data(datadir: str, ticker_interval: int = 5, pairs: Optional[List[str]] = None) -> Dict[str, List]:
    """
    Loads ticker history data for the given parameters
    :param ticker_interval: ticker interval in minutes
    :param pairs: list of pairs
    :return: dict
    """
    path = os.path.abspath(".") #os.path.dirname(__file__))
    result = {}
    for pair in pairs:
        print('loading pair', pair)
        with open('{abspath}/{datadir}/{pair}-{ticker_interval}.json'.format(
            abspath=path,
            datadir=datadir,
            pair=pair,
            ticker_interval=ticker_interval,
        )) as tickerdata:
            result[pair] = json.load(tickerdata)
    return result


def preprocess(strategy: Strategy, tickerdata: Dict[str, List]) -> Dict[str, DataFrame]:
    """Creates a dataframe and populates indicators for given ticker data"""
    processed = {}
    for pair, pair_data in tickerdata.items():
        processed[pair] = populate_indicators(strategy, parse_ticker_dataframe(pair_data))
    return processed

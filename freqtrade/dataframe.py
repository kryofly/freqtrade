"""
Functions to work with pandas dataframes
"""
import os
import json
import logging
from datetime import timedelta
from enum import Enum
from typing import List, Dict

#import arrow
#import talib.abstract as ta
from pandas import DataFrame, to_datetime

#from freqtrade.exchange import get_ticker_history
#from freqtrade.vendor.qtpylib.indicators import crossed_above, crossed_below
#from freqtrade.ta.awesome_oscillator import awesome_oscillator
#from freqtrade.ta.linear_comb import linear_comb

logger = logging.getLogger(__name__)

def load_dataframe(datadir, ticker_interval: int = 5, pairs: [List[str]] = None) -> Dict[str, List]:
    """
    Loads ticker history data for the given parameters
    :param ticker_interval: ticker interval in minutes
    :param pairs: list of pairs
    :return: dict
    """
    path = os.path.abspath('.') # os.path.dirname(__file__))
    result = {}
    if pairs == None:
        raise 'load_dataframe no pairs'
    for pair in pairs:
        print('pair:', pair)
        with open('{abspath}/{datadir}/{pair}-{ticker_interval}.json'.format(
          abspath=path,
          datadir=datadir,
          pair=pair,
          ticker_interval=ticker_interval,
          )) as tickerdata:
               result[pair] = json.load(tickerdata)
    return result


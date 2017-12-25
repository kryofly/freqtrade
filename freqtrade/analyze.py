"""
Functions to analyze ticker data with indicators and produce buy and sell signals
"""
import logging
from datetime import timedelta
from enum import Enum
from typing import List, Dict

import arrow
import talib.abstract as ta
from pandas import DataFrame, to_datetime

from freqtrade.exchange import get_ticker_history
from freqtrade.vendor.qtpylib.indicators import crossed_above, crossed_below
from freqtrade.dataframe import load_dataframe
from freqtrade.strategy import Strategy
from freqtrade.ta.awesome_oscillator import awesome_oscillator
from freqtrade.ta.heikinashi         import heikinashi
from freqtrade.ta.linear_comb import linear_comb

logger = logging.getLogger(__name__)

class SignalType(Enum):
    """ Enum to distinguish between buy and sell signals """
    BUY = "buy"
    SELL = "sell"

def parse_ticker_dataframe(ticker: list) -> DataFrame:
    """
    Analyses the trend for the given ticker history
    :param ticker: See exchange.get_ticker_history
    :return: DataFrame
    """
    columns = {'C': 'close', 'V': 'volume', 'O': 'open', 'H': 'high', 'L': 'low', 'T': 'date'}
    frame = DataFrame(ticker) \
        .drop('BV', 1) \
        .rename(columns=columns)
    frame['date'] = to_datetime(frame['date'], utc=True, infer_datetime_format=True)
    frame.sort_values('date', inplace=True)
    return frame

def populate_indicators(strategy, dataframe: DataFrame) -> DataFrame:
    """
    Adds several different TA indicators to the given DataFrame
    """
    logger.info('---- populating indicators from strategy %s----' % strategy.name())
    inds = strategy.select_indicators(None)  # select indicators according to strategy
    prepare_indicators(strategy, inds, dataframe) # possibly prepare them, before run
    return dataframe

def prepare_indicators(strategy: Strategy, inds: list, dataframe: DataFrame) -> list:
    logger.info('---- preparing indicators ----')
    for ind in inds:
        args = None
        if len(ind) == 1:
            name = ind.pop()
        else:
            args = ind.pop()
            name = ind.pop()
        logger.info('preparing indicator: %s, args=%s' %(name,args))
        new = False
        ali = None
        # Four types of how we call indicators
        # Either using the 'new' flag, that will run the indicator and merge the
        # columns in the resulting dataframe. By doing that, we have no control
        # of the column naming, and it is unfortunate since they collide (stochf and stochrsi)
        if name == 'bbands' or name == 'ht_sine':
            new = True
        if name == 'macd' or name == 'stochf' or name == 'stochrsi':
            new = True
        # The second way, is to call the indicator, assume it will only return a series
        # and add that series to our dataframe with an aliased name: name + first-argument
        # example calling ta.EMA(5) becomes columnname EMA5 in the dataframe
        if name == 'ema':
            ali = True
        # The third way is to call a defclass method which is for more advanced indicators
        # or python-only indicators
        if name == 'heikinashi':
            dataframe[name] = heikinashi(strategy,args).run(dataframe)
        elif name == 'ao':
            dataframe[name] = awesome_oscillator(strategy,args).run(dataframe)
        elif name == 'lin':
            dataframe[name] = linear_comb(strategy,args).run(dataframe)
        else:
          f = getattr(ta,name.upper())
          a = [dataframe]
          a.extend(args or [])
          if new: # this is the cleaned up version
              df = f(*a) # get result of DataFrames
              for col in df.columns: # append each column
                  ser = df[col] # get column from new DF
                  dataframe[col] = ser # and insert it into old DF
          elif ali:
              dataframe[name + str(args[0])] = f(*a)
          else:
              # the fourth way is to use the old way of just simply
              # assuming the indicator function has the same name
              # and returns a series
              dataframe[name] = f(*a)

def analyze_ticker(strategy, ticker_history: List[Dict]) -> DataFrame:
    """
    Parses the given ticker history and returns a populated DataFrame
    add several TA indicators and buy signal to it
    :return DataFrame with ticker data and indicator data
    """
    dataframe = parse_ticker_dataframe(ticker_history)
    dataframe = populate_indicators(strategy, dataframe)
    dataframe = strategy.populate_buy_trend(dataframe)
    dataframe = strategy.populate_sell_trend(dataframe)
    return dataframe

def get_signal(strategy: Strategy, pair: str, signal: SignalType) -> bool:
    """
    Calculates current signal based several technical analysis indicators
    :param pair: pair in format BTC_ANT or BTC-ANT
    :return: True if pair is good for buying, False otherwise
    """
    ticker_hist = get_ticker_history(pair)
    if not ticker_hist:
        logger.warning('Empty ticker history for pair %s', pair)
        return False

    try:
        dataframe = analyze_ticker(strategy, ticker_hist)
    except ValueError as ex:
        logger.warning('Unable to analyze ticker for pair %s: %s', pair, str(ex))
        return False

    if dataframe.empty:
        return False

    latest = dataframe.iloc[-1]

    # Check if dataframe is out of date
    signal_date = arrow.get(latest['date'])
    # aestethically use utcnow, just to avoid arrow bugs in TZ
    # arrow.now() == arrow.utcnow(), just printed differently
    if signal_date < (arrow.utcnow() - timedelta(minutes=10)):
        return False

    result = latest[signal.value] == 1
    logger.info('%s_trigger: %s (pair=%s, signal=%s)', signal.value, latest['date'], pair, result)
    return result

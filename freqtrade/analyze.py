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
from freqtrade.vendor.qtpylib.indicators import awesome_oscillator, crossed_above, crossed_below
from freqtrade.dataframe import load_dataframe
from freqtrade.strategy import Strategy

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
    logger.info('---- populating indicators ----')
    inds = strategy.indicators()

    funs = {'sar': lambda: ta.SAR(dataframe),
            'adx': lambda: ta.ADX(dataframe),
            'fastd': lambda: ta.STOCHF(dataframe)['fastd'],
            'fastk': lambda: ta.STOCHF(dataframe)['fastk'],
            'blower': lambda: ta.BBANDS(dataframe, nbdevup=2, nbdevdn=2)['lowerband'],
            'sma':   lambda: ta.SMA(dataframe, timeperiod=40),
            'tema':  lambda: ta.TEMA(dataframe, timeperiod=9),
            'mfi':   lambda: ta.MFI(dataframe),
            'rsi':   lambda: ta.RSI(dataframe),
            'ema5':  lambda: ta.EMA(dataframe, timeperiod=5),
            'ema10': lambda: ta.EMA(dataframe, timeperiod=10),
            'ema50': lambda: ta.EMA(dataframe, timeperiod=50),
            'ema100':lambda: ta.EMA(dataframe, timeperiod=100),
            'ao':    lambda: awesome_oscillator(dataframe),
            'macd':  lambda: ta.MACD(dataframe)['macd'],
            'macdsignal': lambda: ta.MACD(dataframe)['macdsignal'],
            'macdhist': lambda:   ta.MACD(dataframe)['macdhist'],
            'htsine':     lambda: ta.HT_SINE(dataframe)['sine'],
            'htleadsine': lambda: ta.HT_SINE(dataframe)['leadsine'],
            'plus_dm':  lambda: ta.PLUS_DM(dataframe),
            'plus_di':  lambda: ta.PLUS_DI(dataframe),
            'minus_dm': lambda: ta.MINUS_DM(dataframe),
            'minus_di': lambda: ta.MINUS_DI(dataframe)
            }

    for ind in inds:
        [name, args] = ind
        logger.info('loading indicator: %s' % name)
        dataframe[name] = funs[name]()

    return dataframe

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
    if signal_date < arrow.now() - timedelta(minutes=10):
        return False

    result = latest[signal.value] == 1
    logger.debug('%s_trigger: %s (pair=%s, signal=%s)', signal.value, latest['date'], pair, result)
    return result

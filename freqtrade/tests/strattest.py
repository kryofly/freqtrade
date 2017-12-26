import logging
#import modulelib
import importlib
from functools import reduce
from hyperopt import hp
from pandas import DataFrame
import pandas as pd
import numpy as np
from freqtrade.vendor.qtpylib.indicators import crossed_above, crossed_below

from freqtrade.strategy import Strategy

class XStrategy(Strategy):

    def __init__(self, config=None):
        self.log = logging.getLogger(__name__)
        self.default_config(config)
        
    def name(self):
        return 'test-strategy'

    # what indicators do we use
    def select_indicators(self, some_filter):
        return []

    def stoploss(self, trade, current_rate, current_time, time_diff, current_profit):
        return False

    def populate_buy_trend(self, df: DataFrame) -> DataFrame:
        data = np.array(df['open'].values)
        for i in range(0, len(data)):
            data[i] = 1
        v = pd.Series(index=df.index, data=data)
        df['buy'] = v
        return df

    def populate_sell_trend(self, df: DataFrame) -> DataFrame:
        data = np.array(df['open'].values)
        for i in range(0, len(data)):
            data[i] = 1
        v = pd.Series(index=df.index, data=data)
        df['sell'] = v
        return df

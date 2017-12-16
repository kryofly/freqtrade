import logging
from freqtrade.strategy import Strategy
from functools import reduce
from hyperopt import hp
from pandas import DataFrame
from freqtrade.vendor.qtpylib.indicators import crossed_above, crossed_below

classname = 'LinCombStrategy'

class LinCombStrategy(Strategy):

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.log.info('This is strategy: linear-combination:')
        self.default_config()
        
    def name(self):
        return 'linear-combination'
    
    # what indicators do we use
    def select_indicators(self, some_filter):
      return [['rsi',   None], # A list of indicators used by
              ['ema5',  None], # the linear-combination
              ['ema10', None], # the linear-combination
              # finally a the linear-combination indicator itself,
              ['lin',   {'input':['high','low','rsi','ema5','ema10']}]] # lin, it is here the result of linear-comb is stored

    # what currency pairs do we use for backtesting
    def backtest_pairs(self):
       return ['BTC_ETH'] 

    # for buy and sell descision we only use the linear-combination indicator,
    # becase it has already summed togheter all the other indicators
    def populate_buy_trend(self, dataframe: DataFrame) -> DataFrame:
        if self._hyper_params:
            # FIX: need to see where we are called when we get here, and what we should do
            print('---- using hyper params instead')
            return self.use_hyper_params (dataframe)
        else:
            dataframe.loc[crossed_above(dataframe['lin'], -3), 'buy'] = 1
            return dataframe

    def populate_sell_trend(self, dataframe: DataFrame) -> DataFrame:
        dataframe.loc[crossed_below(dataframe['lin'], -3), 'sell'] = 1
        return dataframe

    # hyper optimize (learn parameters)

    def buy_strategy_space(self):
      return {
        'rsi': hp.choice('rsi', [
            {'enabled': False},
            {'enabled': True, 'value': hp.quniform('rsi-value', 20, 40, 1)}
        ]),
        'ema5': hp.choice('ema5', [
            {'enabled': False},
            {'enabled': True}
        ]),
      }

    def set_hyper_params (self, params):
        self._hyper_params = params
    def use_hyper_params (self, dataframe):
        # We dont use guards and triggers,
        # instead we use the params to guide what indicators to include
        # in the linear-combination, and what parameters those
        # indicators should have
        params = self._hyper_params
        print('--------params:', params)

        conditions = []

        return dataframe

    #
    # Live trading parameters
    # 
    def live_pairs(self):
        return self.backtest_pairs()

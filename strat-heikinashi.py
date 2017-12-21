import logging
from freqtrade.strategy import Strategy
from functools import reduce
from hyperopt import hp
from pandas import DataFrame
from freqtrade.vendor.qtpylib.indicators import crossed_above, crossed_below

classname = 'HeikinAshiStrategy'

class HeikinAshiStrategy(Strategy):

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.log.info('This is strategy: Heikin-Ashi')
        self.default_config()
        self._stake_amount = 0.001 # lower default stake amount, each trades maximum worth

        # adjust, so we dont let stoploss interfere so much

        self._minimal_roi = { '5000':  0.0,  # put silly amount to really ride the profits
                              '4000':  0.01,
                              '2000':  0.02,
                              '1000':  0.04
                            }
        self._stoploss = -0.20    # absolutly exit if we go below buy price by this ratio
        self._stoploss_glide = -0.10 # larger room for movement if we go below the stoploss-floor
        self._stoploss_glide_ema = 0.005 # lift the exit-floor slower

    def name(self):
        return 'heikin-ashi'

    # what indicators do we use
    def select_indicators(self, some_filter):
      return [['heikinashi',   None], # A list of indicators used by
             ]

    # what currency pairs do we use for backtesting
    def backtest_pairs(self):
       return [
          # big coins
         'BTC_ETH',  'BTC_LTC',  'BTC_BCC', 'BTC_DASH',
         'BTC_XRP',
          # mid-small coins
         'BTC_ADA',
         'BTC_BAT',
         'BTC_ERC',  'BTC_ETC',  'BTC_EMC2',
         'BTC_GNO',  'BTC_GRS',
         'BTC_NEO', 
         'BTC_MER',  'BTC_MCO',
         'BTC_OK' ,  'BTC_OMG',
         'BTC_LSK',
         'BTC_PIVX', 'BTC_POWR',
         'BTC_SIB',  'BTC_STRAT',
         'BTC_VTC',
         'BTC_QTUM', 'BTC_WAVES',
         'BTC_XLM',  'BTC_XEM',  'BTC_XZC',
         ]

    # use the Heikin-Ashi candlestick to
    # figure out buy and sell points
    def populate_buy_trend(self, dataframe: DataFrame) -> DataFrame:
        if self._hyper_params:
            raise NameError('hyperopt is NIY for Heikin-Ashi candlesticks.')
        else:
            # Notice, normal open,close,high,low has been
            # replaced with the Heikin-Ashi version
                          # current stick is green/bull/hollow
            dataframe.loc[(dataframe['open'] < dataframe['close'])
                          # and two previous was also green
                          & (dataframe['open'].shift(1) < dataframe['close'].shift(1))
                          & (dataframe['open'].shift(2) < dataframe['close'].shift(2))
                          # check oldest green comes before a red
                          & (dataframe['open'].shift(2) < dataframe['close'].shift(3))
                          # three consecutive days of red sticks
                          & (dataframe['open'].shift(3) > dataframe['close'].shift(3))
                          & (dataframe['open'].shift(4) > dataframe['close'].shift(4))
                          & (dataframe['open'].shift(5) > dataframe['close'].shift(5))
                          ,'buy'] = 1
            return dataframe

    def populate_sell_trend(self, dataframe: DataFrame) -> DataFrame:
                      # current stick is red/bear/filled
        dataframe.loc[(dataframe['open'] > dataframe['close'])
                      # and previous two sticks was also red
                      & (dataframe['open'].shift(1) > dataframe['close'].shift(1))
                      & (dataframe['open'].shift(2) > dataframe['close'].shift(2))
                      # perhaps check for three consecutive days of lower relative closes
                      & (dataframe['close']          < dataframe['close'].shift(1))
                      & (dataframe['close'].shift(1) < dataframe['close'].shift(2))
                      ,'sell'] = 1
        return dataframe


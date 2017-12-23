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

        self._minimal_roi = { '8000':  0.2,  # put silly amount to really ride the profits
                              '4000':  0.3,
                              '2000':  0.4,
                              '1000':  0.5   # a 50% profit so quick is bound to be reversed, so take it
                            }
        self._stoploss = -0.10    # absolutly exit if we go below buy price by this ratio
        self._stoploss_glide = -0.10 # larger room for movement if we go below the stoploss-floor
        self._stoploss_glide_ema = 0.01 # lift the exit-floor slower

    def name(self):
        return 'heikin-ashi'

    # what indicators do we use
    def select_indicators(self, some_filter):
      return [['heikinashi', None], # A list of indicators used by
              ['rsi',       [33]],
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
            dataframe.loc[  # current and previous bar is green/hollow
                            (dataframe['ha_open']          < dataframe['ha_close'])          # green bar
                          & (dataframe['ha_open'].shift(1) < dataframe['ha_close'].shift(1)) # green bar
                          & (dataframe['ha_low' ].shift(1) > dataframe['ha_low'  ].shift(2)) # higher low

                          & (dataframe['ha_open'].shift(2) > dataframe['ha_close'].shift(2)) # red bar
                          & (dataframe['ha_open'].shift(3) > dataframe['ha_close'].shift(3)) # red bar
                          & (dataframe['ha_open'].shift(4) > dataframe['ha_close'].shift(4)) # red bar
                          & (dataframe['ha_open'].shift(5) > dataframe['ha_close'].shift(5)) # red bar
                          # For good measure, throw some oscillator in the pot
                          & (dataframe['rsi'] < 40)

                          ,'buy'] = 1
            return dataframe

    def populate_sell_trend(self, dataframe: DataFrame) -> DataFrame:
                      # current stick is red/bear/filled
        dataframe.loc[
                        (dataframe['ha_open']          > dataframe['ha_close'])          # red bar
                      & (dataframe['ha_open'].shift(1) > dataframe['ha_close'].shift(1)) # red bar
                      & (dataframe['ha_high'].shift(1) < dataframe['ha_high' ].shift(2)) # lower high
                      & (dataframe['ha_open'].shift(2) < dataframe['ha_close'].shift(2)) # green bar
                      & (dataframe['ha_open'].shift(3) < dataframe['ha_close'].shift(3)) # green bar
                      & (dataframe['ha_open'].shift(4) < dataframe['ha_close'].shift(4)) # green bar
                      & (dataframe['ha_open'].shift(5) < dataframe['ha_close'].shift(5)) # green bar
                      # For good measure, throw some oscillator in the pot
                      & (dataframe['rsi'] > 60)

                      ,'sell'] = 1
        return dataframe


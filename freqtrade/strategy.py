from typing import Dict, Optional, List
import logging
#import modulelib
import importlib
from functools import reduce
from hyperopt import hp
from pandas import DataFrame
from freqtrade.vendor.qtpylib.indicators import crossed_above, crossed_below


# @property descriptors doesn't get rid of the boilerplate
def getset(obj, slot, val):
   if val is None:
       return obj.__dict__[slot]
   else:
       obj.__dict__[slot] = val
       return val

class Strategy():

    def __init__(self, config=None):
        self.log = logging.getLogger(__name__)
        self.default_config(config)

    def default_config(self, config=None):
        #### Edit these
        #### [0,1] means a float having a value anywhere (and including) from 0 to 1
        self._backtest_pairs = ['BTC_ETH'] # what pairs to use for backtesting
        self._stake_currency = 'BTC' # base currency
        self._stake_amount = 0.01 # each trades maximum worth
        self._max_open_trades = 3 # concurrently ongoing trades
        self._tick_interval   = 5 # what minute data to use
        self._ask_last_balance = 0 # [0,1] buy price from last to ask
        self._minimal_roi = { '40':  0.0,
                              '30':  0.01,
                              '20':  0.02,
                              '0':  0.04
                            }
        self._stoploss = -0.10    # exit if we go below buy price by this ratio
        self._stoploss_glide = -0.05 # exit if we go this ratio below gliding stop
        self._stoploss_glide_ema = 0.01  # how fast we update the gliding stoploss,
                                         # a ratio that picks this amount from
                                         # current pricerate
        #### Dont edit these
        self._stoploss_glide_rate = None
        self._hyper_params = None
        self._config = config

    def load(self, filename):
        if filename is not None:
            self.log.info('loading file: %s' % filename)
            mod = importlib.__import__(filename)
            classname = mod.classname
            cl = getattr(mod, classname)
            return cl(self._config)
        else:
            self.log.info('using default strategy')
            return self

    def name(self):
        return 'default'

    # what indicators do we use
    def select_indicators(self, some_filter):
        self.log.info('selecting all indicators (default)')
        return [['sar',        ],
                ['adx',        ],
              # ['stochf', [5,3]], # fastk-, fastd- period
                # gives 'fastk' and 'fastd'
                ['stochrsi', [14, 5, 3]],
                # stochrsi also gives fastk and fastd
                ['bbands',     [2,2]], # nbdevup, nbdevdn
                # gives 'upperband', 'middleband', 
                #       and 'lowerband'
                ['sma',        [40]],
                ['tema',       [9]],
                ['mfi',        ],
                ['ao',         {'fast':5, 'slow':34}],
                # Calculate rsi on the previous AO oscillator
                # instead of using the default 'close'
                # stating timeperiod is not needed (default 14)
                ['rsi', {'price':'ao', 'timeperiod':14}],
                #['rsi', [14]], # default to 14 periods,
                # all ema will output name ema+len:
                ['ema',      [5]], # name is ema5
                ['ema',     [10]],
                ['ema',     [50]],
                ['ema',    [100]],
                ['macd',       ],
                # gives 'macd', 'macdsignal' and 'macdhist'
                ['ht_sine',     ],
                # gives 'sine' and 'leadsine'
                ['plus_dm',    ],
                ['plus_di',    ],
                ['minus_dm',   ],
                ['minus_di',   ]]

    # what currency pairs do we use for backtesting
    def backtest_pairs(self):
       return self._backtest_pairs

    def set_backtest_pairs(self, pairs):
       self._backtest_pairs = pairs

    def tick_interval(self):
        return self._tick_interval

    def stake_currency(self):
        return self._stake_currency

    def stake_amount(self):
        return self._stake_amount

    def max_open_trades(self):
        return self._max_open_trades

    def minimal_roi(self):
        return self._minimal_roi

    # exit trade, due to stoploss, duration, ROI reached, etc
    def stoploss(self, trade, current_rate, current_time, time_diff, current_profit):

        # Exit trade du to ROI or duration timeout

        # Check if time matches and current rate is above threshold
        for duration, threshold in sorted(self.minimal_roi().items()):
            if time_diff > float(duration) and current_profit > threshold:
                self.log.info('current_profit=%s > min_roi_treshold=%s AND %s frames is > limit=%s'
                      %(current_profit, threshold, time_diff, duration))
                return True

        # check for simple stoploss

        if(current_profit < self._stoploss):
            self.log.info('stoploss hit due to current_profit=%s < stoploss=%s' % (current_profit, self._stoploss))
            return True

        # check for gliding stoploss

        sl_glide_rate = trade.stat_stoploss_glide_rate
        if sl_glide_rate:
            # check if the gliding stoploss has hit
            if (current_rate / sl_glide_rate - 1) < self._stoploss_glide:
                self.log.info('stoploss trail hit: rate=%s, glide=%s, stop=%s' %(current_rate, sl_glide_rate, self._stoploss_glide))
                return True

        return False

    def step_frame(self, trade, current_rate, date):
        #
        # update gliding stoploss
        #

        # current gliding stoploss rate for this trade
        sl_glide_rate = trade.stat_stoploss_glide_rate
        # set current stoploss pricerate at current rate, if not set
        if not sl_glide_rate:
            self.log.info('%s initializing stoploss_glide_rate to %s' %(date, current_rate))
            sl_glide_rate = trade.stat_stoploss_glide_rate = current_rate

        # exponential update the gliding stoploss
        sl_glide = self._stoploss_glide_ema  # ratio of how fast we move the gliding stoploss
        sl_glide_target = current_rate
        if trade.stat_max_rate and trade.stat_max_rate > sl_glide_target:
            sl_glide_target = trade.stat_max_rate

        # let gliding stoploss slowly converge to the maximal seen rate
        sl_glide_rate = (1 - sl_glide) * sl_glide_rate + sl_glide * sl_glide_target
        # update the glide_rate in the trade
        self.log.info('%s adjust stoploss trail %.7f -> %.7f towards %.7f (current_rate=%s)' %(date, trade.stat_stoploss_glide_rate, sl_glide_rate, sl_glide_target, current_rate))
        trade.stat_stoploss_glide_rate = sl_glide_rate # this is why we must persistence every frame

    def populate_buy_trend(self, dataframe: DataFrame) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        if self._hyper_params:
            return self.use_hyper_params (dataframe)
        else:
            dataframe.loc[crossed_above(dataframe['rsi'], 30)
                          , 'buy'] = 1

            return dataframe

    def populate_sell_trend(self, dataframe: DataFrame) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            crossed_below(dataframe['rsi'], 70)
            ,
            'sell'] = 1
        return dataframe

    # hyper optimize (learn parameters)

    def buy_strategy_space(self):
      return {
        'mfi': hp.choice('mfi', [
            {'enabled': False},
            {'enabled': True, 'value': hp.quniform('mfi-value', 5, 25, 1)}
        ]),
        'fastd': hp.choice('fastd', [
            {'enabled': False},
            {'enabled': True, 'value': hp.quniform('fastd-value', 10, 50, 1)}
        ]),
        'adx': hp.choice('adx', [
            {'enabled': False},
            {'enabled': True, 'value': hp.quniform('adx-value', 15, 50, 1)}
        ]),
        'rsi': hp.choice('rsi', [
            {'enabled': False},
            {'enabled': True, 'value': hp.quniform('rsi-value', 20, 40, 1)}
        ]),
        'uptrend_long_ema': hp.choice('uptrend_long_ema', [
            {'enabled': False},
            {'enabled': True}
        ]),
        'uptrend_short_ema': hp.choice('uptrend_short_ema', [
            {'enabled': False},
            {'enabled': True}
        ]),
        'over_sar': hp.choice('over_sar', [
            {'enabled': False},
            {'enabled': True}
        ]),
        'green_candle': hp.choice('green_candle', [
            {'enabled': False},
            {'enabled': True}
        ]),
        'uptrend_sma': hp.choice('uptrend_sma', [
            {'enabled': False},
            {'enabled': True}
        ]),
        'trigger': hp.choice('trigger', [
            {'type': 'lower_bb'},
            {'type': 'faststoch10'},
            {'type': 'ao_cross_zero'},
            {'type': 'ema5_cross_ema10'},
            {'type': 'macd_cross_signal'},
            {'type': 'sar_reversal'},
            {'type': 'stochf_cross'},
            {'type': 'ht_sine'},
        ]),
      }

    def set_hyper_params (self, params):
        self._hyper_params = params
    def use_hyper_params (self, dataframe):
        params = self._hyper_params
        conditions = []
        # GUARDS AND TRENDS
        if params['uptrend_long_ema']['enabled']:
            conditions.append(dataframe['ema50'] > dataframe['ema100'])
        if params['uptrend_short_ema']['enabled']:
            conditions.append(dataframe['ema5'] > dataframe['ema10'])
        if params['mfi']['enabled']:
            conditions.append(dataframe['mfi'] < params['mfi']['value'])
        if params['fastd']['enabled']:
            conditions.append(dataframe['fastd'] < params['fastd']['value'])
        if params['adx']['enabled']:
            conditions.append(dataframe['adx'] > params['adx']['value'])
        if params['rsi']['enabled']:
            conditions.append(dataframe['rsi'] < params['rsi']['value'])
        if params['over_sar']['enabled']:
            conditions.append(dataframe['close'] > dataframe['sar'])
        if params['green_candle']['enabled']:
            conditions.append(dataframe['close'] > dataframe['open'])
        if params['uptrend_sma']['enabled']:
            prevsma = dataframe['sma'].shift(1)
            conditions.append(dataframe['sma'] > prevsma)

        # TRIGGERS
        triggers = {
            'lower_bb': dataframe['tema'] <= dataframe['lowerband'],
            'faststoch10': (crossed_above(dataframe['fastd'], 10.0)),
            'ao_cross_zero': (crossed_above(dataframe['ao'], 0.0)),
            'ema5_cross_ema10': (crossed_above(dataframe['ema5'], dataframe['ema10'])),
            'macd_cross_signal': (crossed_above(dataframe['macd'], dataframe['macdsignal'])),
            'sar_reversal': (crossed_above(dataframe['close'], dataframe['sar'])),
            'stochf_cross': (crossed_above(dataframe['fastk'], dataframe['fastd'])),
            'ht_sine': (crossed_above(dataframe['leadsine'], dataframe['sine'])),
        }
        conditions.append(triggers.get(params['trigger']['type']))

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            'buy'] = 1

        return dataframe

    #
    # Live trading parameters
    # 
    def live_pairs(self):
        return self.backtest_pairs()

    #
    # bid/ask strategy
    # These should be enabled so that we can
    # differentiate on exchange,
    # for that to happen we need a 'env' variable
    # given here
    #

    def ask_last_balance(self, val=None):
        return getset(self, '_ask_last_balance', val)

    def get_target_bid(self, ticker: Dict[str, float]) -> float:
        if ticker['ask'] < ticker['last']:
            return ticker['ask']
        balance = self._ask_last_balance
        return ticker['ask'] + balance * (ticker['last'] - ticker['ask'])

    #
    # Environment
    # Not exactly trading specific
    #
    def whitelist(self):
        if self._config and 'exchange' in self._config:
            ex = self._config['exchange']
            if 'pair_whitelist' in ex:
                return ex['pair_whitelist']
        return None

    def set_whitelist(self, whitelist):
        if self._config and 'exchange' in self._config:
            ex = self._config['exchange']
            self._config['exchange']['pair_whitelist'] = whitelist
            return True
        return False

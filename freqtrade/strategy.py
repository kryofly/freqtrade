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
        # Document under what circumstances self._hyper_params is set
        # If hyperopt is running, params will be set, and that means we
        # are inside an hyperopt-learning-iteration (epoch), and should
        # use the params to build up an indicator list with learned arguments,
        # and return that. Hyperopt will take that list, and test how good it is.
        # If not running hyperopt (example only backttesting, then params is empty)
        params = self._hyper_params
        if params:
            # Use the params, to figure out what indicators
            # to use, and what parameters to give them
            return [['rsi', 'rsi', {'price':'close', 'timeperiod':14}],
                    ['ema', 'ema',      [5]], # name is ema5
                    ]
        else:
            # This is backtesting and Live parameters to use.
            # These should be updated to the best one found
            # by hyperopt
            self.log.info('selecting all indicators (default)')
            return [['rsi', 'rsi', {'price':'close', 'timeperiod':14}],
                    ['ema', 'ema',      [5]], # name is ema5
                    ]

    # what currency pairs do we use for backtesting
    def backtest_pairs(self):
       return self._backtest_pairs

    def set_backtest_pairs(self, pairs):
       self._backtest_pairs = pairs

    def tick_interval(self):
        return self._tick_interval

    def fee(self):
        return 0.0025 # what fee to use during backtesting/hyperopt

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
                #self.log.info('current_profit=%s > min_roi_treshold=%s AND %s frames is > limit=%s'
                #      %(current_profit, threshold, time_diff, duration))
                return True

        # check for simple stoploss

        if(current_profit < self._stoploss):
            #self.log.info('stoploss hit due to current_profit=%s < stoploss=%s' % (current_profit, self._stoploss))
            return True

        # check for gliding stoploss

        sl_glide_rate = trade.stat_stoploss_glide_rate
        if sl_glide_rate:
            # check if the gliding stoploss has hit
            if (current_rate / sl_glide_rate - 1) < self._stoploss_glide:
                #self.log.info('stoploss trail hit: rate=%s, glide=%s, stop=%s' %(current_rate, sl_glide_rate, self._stoploss_glide))
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
        #self.log.info('%s adjust stoploss trail %.8f -> %.8f towards %.8f (current_rate=%s)' %(date, trade.stat_stoploss_glide_rate, sl_glide_rate, sl_glide_target, current_rate))
        trade.stat_stoploss_glide_rate = sl_glide_rate # this is why we must persistence every frame

    def populate_buy_trend(self, dataframe: DataFrame) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        params = self._hyper_params
        if params:
            print('----------- params:', params)
            dataframe.loc[(dataframe['rsi'] < params['rsi_bull'])
                          ,'buy'] = 1
            return dataframe
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
        params = self._hyper_params
        if params:
            dataframe.loc[(dataframe['rsi'] > params['rsi_bear'])
                          ,'sell'] = 1
            return dataframe
        else:
            # Edit: use the best parameters found
            dataframe.loc[(dataframe['rsi'] > 70)
                          ,'sell'] = 1
            return dataframe

    # hyper optimize (learn parameters)

    def strategy_space(self):
      return {'rsi_bull': hp.quniform('rsi_bull_value', 10, 40, 1),
              'rsi_bear': hp.quniform('rsi_bear_value', 60, 90, 1)
             }

    def set_hyper_params (self, params):
        self._hyper_params = params

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

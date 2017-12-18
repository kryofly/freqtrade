import logging
#import modulelib
import importlib
from functools import reduce
from hyperopt import hp
from pandas import DataFrame
from freqtrade.vendor.qtpylib.indicators import crossed_above, crossed_below

class Strategy():

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.default_config()
        
    def default_config(self):
        #### Edit these
        self._stake_currency = 'BTC', # base currency
        self._stake_amount = 0.01 # each trades maximum worth
        self._max_open_trades = 3 # concurrently ongoing trades
        self._tick_interval   = 5 # what minute data to use
        self._minimal_roi = { '40':  0.0,
                              '30':  0.01,
                              '20':  0.02,
                              '0':  0.04
                            }
        self._stoploss = -0.10
        #### Dont edit from these
        self._hyper_params = None
        
    def load(self, filename):
        if filename is not None:
            self.log.info('loading file: %s' % filename)
            mod = importlib.__import__(filename)
            classname = mod.classname
            cl = getattr(mod, classname)
            return cl()
        else:
            self.log.info('using default strategy')
            return self

    def name(self):
        return 'default'

    def stoploss(trade, current_rate, current_time, time_diff, current_profit):
        if(current_profit < _stoploss):
            return True
        return False

    # what indicators do we use
    def select_indicators(self, some_filter):
        self.log.info('selecting all indicators (default)')
        return [['sar',        None],
                ['adx',        None],
                ['fastd',      None],
                ['fastk',      None],
                ['blower',     None],
                ['sma',        None],
                ['tema',       None],
                ['mfi',        None],
                ['rsi',        None],
                ['ema5',       None],
                ['ema10',      None],
                ['ema50',      None],
                ['ema100',     None],
                ['ao',         {'fast':5, 'slow':34}],
                ['macd',       None],
                ['macdsignal', None],
                ['macdhist',   None],
                ['htsine',     None],
                ['htleadsine', None],
                ['plus_dm',    None],
                ['plus_di',    None],
                ['minus_dm',   None],
                ['minus_di',   None]]

    # what currency pairs do we use for backtesting
    def backtest_pairs(self):
       return ['BTC_ETH'] 

    def stake_currency(self):
        return self._stake_currency

    def stake_amount(self):
        return self._stake_amount

    def max_open_trades(self):
        return self._max_open_trades

    def minimal_roi(self):
        return self._minimal_roi

    def stoploss(self, trade, current_rate, current_time, time_diff, current_profit):
        if(current_profit < self._stoploss):
            return True
        return False

    def tick_interval(self):
        return self._tick_interval
    
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
            'lower_bb': dataframe['tema'] <= dataframe['blower'],
            'faststoch10': (crossed_above(dataframe['fastd'], 10.0)),
            'ao_cross_zero': (crossed_above(dataframe['ao'], 0.0)),
            'ema5_cross_ema10': (crossed_above(dataframe['ema5'], dataframe['ema10'])),
            'macd_cross_signal': (crossed_above(dataframe['macd'], dataframe['macdsignal'])),
            'sar_reversal': (crossed_above(dataframe['close'], dataframe['sar'])),
            'stochf_cross': (crossed_above(dataframe['fastk'], dataframe['fastd'])),
            'ht_sine': (crossed_above(dataframe['htleadsine'], dataframe['htsine'])),
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

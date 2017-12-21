from freqtrade.ta.ta import TA

class heikinashi(TA):
    def __init__(self, strategy, args):
        self.strategy = strategy
        # first call the superclass main to handle common setup (boilerplate)
        print('heikinashi create instance, args=%s' % args)
        self.main(strategy, args)

    def set_params(self, stategy, args):
        return None

    def run_ind(self, bars):
        bars = bars.copy() # this look expensive
        bars['ha_close'] = (bars['open'] + bars['high'] +
                            bars['low'] + bars['close']) / 4
        bars['ha_open'] = (bars['open'].shift(1) + bars['close'].shift(1)) / 2
        bars.loc[:1, 'ha_open'] = bars['open'].values[0]
        bars.loc[1:, 'ha_open'] = (
            (bars['ha_open'].shift(1) + bars['ha_close'].shift(1)) / 2)[1:]
        bars['ha_high'] = bars.loc[:, ['high', 'ha_open', 'ha_close']].max(axis=1)
        bars['ha_low'] = bars.loc[:, ['low', 'ha_open', 'ha_close']].min(axis=1)
        return self.series(bars, data={'open':  bars['ha_open'],
                                       'high':  bars['ha_high'],
                                       'low':   bars['ha_low'],
                                       'close': bars['ha_close']})

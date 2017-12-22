from freqtrade.ta.ta import TA

class heikinashi(TA):
    def __init__(self, strategy, args):
        self.strategy = strategy
        # first call the superclass main to handle common setup (boilerplate)
        print('heikinashi create instance, args=%s' % args)
        self.main(strategy, args)

    def set_params(self, stategy, args):
        return None

    def run_ind(self, obars):
        obars['ha_close'] = (obars['open'] + obars['high'] +
                             obars['low']  + obars['close']) / 4
        obars['ha_open']  = (obars['open'].shift(1) + obars['ha_close'].shift(1)) / 2
        obars.loc[:1, 'ha_open'] = obars['open'].values[0]
        obars.loc[1:, 'ha_open'] = (
            (obars['ha_open'].shift(1) + obars['ha_close'].shift(1)) / 2)[1:]

        obars['ha_high'] = obars.loc[:, ['high', 'ha_open', 'ha_close']].max(axis=1)
        obars['ha_low']  = obars.loc[:, ['low' , 'ha_open', 'ha_close']].min(axis=1)

        return self.series(obars, data=obars['ha_open'])

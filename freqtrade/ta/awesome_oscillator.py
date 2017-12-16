from freqtrade.ta.ta import TA

class awesome_oscillator(TA):
    def __init__(self, strategy, args):
        self.strategy = strategy
        # first call the superclass main to handle common setup (boilerplate)
        print('awesome create instance, args=%s' % args)
        self.main(strategy, args)

    def set_params(self, stategy, args):
        self.log.info('---------- awesome_oscillator set_params -------------')
        self.log.info('args: %s' % args)
        self.weighted = args.setdefault('weighted', False)
        self.fast     = args.setdefault('fast', 5)
        self.slow     = args.setdefault('slow', 34)

    def run_ind(self, df):
        self.log.info('---------- run awesome_oscillator -------------')
        midprice = (df['high'] + df['low']) / 2

        if self.weighted:
            ao = (midprice.ewm(self.fast).mean() - midprice.ewm(self.slow).mean()).values
        else:
            ao = self.numpy_rolling_mean(midprice, self.fast) - \
                self.numpy_rolling_mean(midprice, self.slow)
        return self.series(df, ao)

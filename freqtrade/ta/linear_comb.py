import numpy as np

from freqtrade.ta.ta import TA

class linear_comb(TA):
    def set_params(self, args):
        self.log.info('---------- linear_comb set_params -------------')
        self.df       = args['df']
        self.input    = args['input']

    def run(self):
        df = self.df
        input = self.input
        # collect the indicators appointed to by the input, these
        # zip together the arrays making a matrix of time(row) x inputs(columns)
        # loop over the rows (where each row is a timeframe of indicators)
        # take the dot product between the row and our weights
        # store the product as output for this timeframe
        self.log.info('---------- running linear_comb -------------')
        self.log.info('input: %s', input)
        midprice = (df['high'] + df['low']) / 2

        return self.series(midprice)

    def __init__(self, args):
        self.main(args)

    def _init_weights(len):
        self.weights = np.random.randn(len) * 0.01

    def _lincomb(input):
        return np.dot(self.weights, self._feature_vector(input))

    def _feature_vector(input):
        ilen = len(input) # input vector
        olen = ilen * 4   # output some non-linearity
        o = np.empty(olen)
        bf = 10 # bleed-factor, [1,inf] higher: reduce bleed on this param
        br = 0.99 # bleed-rate [1,0] lower: more bleeding from other params
        b = 0 # bleed
        for t in xrange(ilen):
            t2 = np.abs(t - 1);
            v[t] = input[ilen] # linear version of the input
            v[t+ilen]   = input[ilen] * input[ilen] # 1-degree non-linear of input
            # do some fancy non-linearization
            v[t+ilen*2] = input[ilen] + input[ilen-t2] + m / bf # summarize+bleed
            v[t+ilen*3] = input[ilen] * input[ilen-t2] + m / bf # cross-over+bleed
            m = m * br + (v[t+ilen*2] + v[t+ilen*3]) * (1 - br) # bleed over
        return v

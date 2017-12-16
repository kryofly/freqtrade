import numpy as np

from freqtrade.ta.ta import TA

class linear_comb(TA):
    def __init__(self, strategy, args):
        #print('--- func in init:', self) # check if we are using the same object
        self._strategy = strategy # we need to set it here (cant do it in set_params)
        self.main(strategy, args)

    def set_params(self, strategy, args):
        self.log.info('---------- linear_comb set_params -------------')
        self.input    = args['input']
        self.stategy  = strategy # why doesn't this work?
        #print('--- func in set_params:', self)

    # above was only boilerplate, below is linear-combination stuff

    def run_ind(self, df):
        inputnames = self.input
        #print('--- func in run_ind:', self)
        strat = self._strategy
        # collect the indicators appointed to by the input, these
        # zip together the arrays making a matrix of time(row) x inputs(columns)
        # loop over the rows (where each row is a timeframe of indicators)
        # take the dot product between the row and our weights
        # store the product as output for this timeframe
        
        # Note, the weights as for now, comes from a mythical place

        self.log.info('---------- running linear_comb under strategy %s -------------' % strat.name())
        self.log.info('input: %s', inputnames)
        input = np.column_stack([df[x].tolist() for x in inputnames])
       
        self.log.info(input)
        
        # HERE IS THE ACTION 2017-12-16 17:00 CET
        
        # input is now a matrix where row is time, and column is feature
        # todo: take this input, and for each row:
        #   take dotproduct of row and weights (just element-multiply and sum)
        #   and put the result in df['lin][row-number]

        output = (df['high'] + df['low']) / 2 # this is just a placeholder for now

        return self.series(df, output)

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
            v[t+ilen*2] = input[ilen] - input[ilen-t2] + m / bf # difference+bleed
            v[t+ilen*3] = input[ilen] * input[ilen-t2] + m / bf # cross-over+bleed
            m = m * br + (v[t+ilen*2] + v[t+ilen*3]) * (1 - br) # bleed over
        return v

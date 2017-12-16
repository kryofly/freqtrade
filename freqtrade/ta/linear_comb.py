import numpy as np

from freqtrade.ta.ta import TA

# to use this:
# run: freqtrade -s strat-lincomb backtesting

# this will create a weights file 'w'

# this file will need to be trained using the feature-vector and input.
# FIX: those are also saved to 'f' and 'x'

class linear_comb(TA):
    def __init__(self, strategy, args):
        #print('--- func in init:', self) # check if we are using the same object
        self._strategy = strategy # we need to set it here (cant do it in set_params)
        self.main(strategy, args)

    def set_params(self, strategy, args):
        #print('--- func in set_params:', self)
        self.log.info('---------- linear_comb set_params -------------')
        # we could put the weights-filename in the args
        #self.weightsfile = args['weightsfile']
        self.input    = args['input']
        self.stategy  = strategy # why doesn't this work?
        try:
            self._weights = np.loadtxt('w')
            self.log.info('---------- loaded (hopefully) pretrained weights  -------------')
        except FileNotFoundError:
            self._init_weights(len(self.input) * 4)
            np.savetxt('w', self._weights)

    # above is mostly boilerplate, below is the linear-combination stuff

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

        # input is now a matrix where row is time, and column is feature
        # lincomb will feature-expand the input (do some simple non-linearity)
        # then take dotproduct of row and weights (just element-multiply and sum)
        # and put the result in df['lin]
        z = self._lincomb(input)

        # need to load the weights from disk, where they have been pre-trained
        w = self._weights # retreive the weights from the mythical place

        rows, = z.shape
        for i in range(rows):
          print('lin ind: %s %s' % (df['date'][i], z[i]))

        return self.series(df, z)

    # this is used to create a fresh set of weights, when we have none
    # this set obviously needs to be trained
    def _init_weights(self, len):
        self._weights = np.random.randn(len) * 0.01
        return self._weights

    def _lincomb(self, input):
        return np.inner(self._weights, self._feature_vector(input))

    def _feature_vector(self, input):
        rows,cols = input.shape
        ocols = cols * 4  # expand the output with some non-linearity 
        o = np.empty([rows, ocols])
        bf = 10 # bleed-factor, [1,inf] higher: reduce bleed on this param
        br = 0.99 # bleed-rate [1,0] lower: more bleeding from other params
        for i in range(rows):
            b = 0 # bleed
            i1 = i - 1;
            i2 = i - 2;
            if i1 < 0:
                i2 = 0
            if i2 < 0:
                i2 = 0
            for j in range(cols):
                j2 = np.abs(j - 1);
                jj = j % cols
                o[i][j]        = input[i][jj] # linear version of the input
                o[i][j+cols]   = input[i][jj] * input[i][jj] # 1-degree non-linear of input
                # do some fancy non-linearization
                o[i][j+cols*2] = input[i][jj]  - input[i][j2]  + b / bf # difference+bleed
                o[i][j+cols*3] = input[i1][jj] - input[i2][jj] + b / bf # temporal+bleed
                b = b * br + (o[i][j+cols*2] + o[i][j+cols*3]) * (1 - br) # bleed over
        return o

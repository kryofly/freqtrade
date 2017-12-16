
import logging
import pandas as pd
from enum import Enum

from freqtrade.vendor.qtpylib.indicators import numpy_rolling_mean, numpy_rolling_std

class TA():
    """Base class for TA indicators/oscillators
    Individual indicators/oscillators should subclass this class
    and override the set_params() and run() methods

    Individual (instances) can also override the followin methods
    for customization:
    - preamble() -- do any initialization of the indicator (test data is available)
    - postamble() -- do any result reporting analysis

    The __init__() and main() methods should not be overridden.
    This class also contains various public and private helper methods."""

    def __init__(self, args):
        """Sets TA framwork defaults. Do not override this method."""

    def main(self, args):
        """Main function. Do not override this method."""
        self._log_prefix()
        self.set_params(args)
        # do any TA options handling
        try:
            return self.run()
        except NAerror as e:
            self.log.exception("IND error N/A: %s" % e.message)
            return []

        # take care of any results, that can be handled commonly
        self.log.info("doing IND cleanup")
        #self._stop_logging()
        return self.result

    def run(self):
        """IND is not implemented"""
        raise NotImplementedError

    def numpy_rolling_mean(self,a,b):
        return numpy_rolling_mean(a,b)
    def numpy_rolling_std(self,a,b):
        return numpy_rolling_std(a,b)
    def series(self, data):
        return pd.Series(index=self.df.index, data=data)

    # private helper methods, subclass instances should not use these
    def _log_prefix(self): # change the log-prefix
        self.log = logging.getLogger(__name__)


class NAerror(Exception):
    """This exception is raised when IND is N/A to current data"""
    def __init__(self, message):
        self.message = message

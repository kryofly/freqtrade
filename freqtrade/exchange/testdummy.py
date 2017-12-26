import logging
import random
import time
from typing import List, Dict
from requests.exceptions import ContentDecodingError

from freqtrade.exchange.interface import Exchange

class Testdummy(Exchange):
    """
    Dummy exchange for testing,
    dont trade live with this.
    """
    def __init__(self, config):
        self.conf = config
        self.log = logging.getLogger(__name__)
        self._pairs = dict() # what pairs we are currenty holding
        self._events = [] # log all actions

    # Test parameters

    # Probability with exchange problem
    #@property
    def _test_failrate(self) -> float:
        #return 0.1 # Expected: every 10th other request will fail
        return self.conf['failrate']

    def sim_fail(self):
        if random.random() > self._test_failrate():
            return False
        else:
            return True

    def _make_uuid(self):
        return format('AAAA%x' %(int(random.random() *
                                     pow(10,16))))

    # Use a property?
    def get_events(self):
        return self._events

    # Exchange API

    # Use the same fees as https://bittrex.com/fees
    @property
    def fee(self) -> float:
        return 0.0025

    def buy(self, pair: str, rate: float, amount: float) -> str:
        # record {pair, amount, rate}
        if self.sim_fail():
            raise OperationalException('{message} params=({pair}, {rate}, {amount})'.format(
                message='Exchangedummy Buy failed',
                pair=pair,
                rate=rate,
                amount=amount))
        else:
            uuid = self._make_uuid()
            self._pairs[uuid] = [pair, rate, amount, 'LIMIT_BUY']
            # FIX: log event
            return uuid

    def sell(self, pair: str, rate: float, amount: float) -> str:
        if self.sim_fail():
            raise OperationalException('{message} params=({pair}, {rate}, {amount})'.format(
                message='Exchangedummy Sell failed',
                pair=pair,
                rate=rate,
                amount=amount))
        for uuid, rec in self._pairs.items():
            [pair2, rate2, amount2, order_type] = rec
            if pair2 == pair and order_type == 'LIMIT_BUY':
                rec[3] = 'LIMIT_SELL'
                return uuid
        return None

    def get_balance(self, currency: str) -> float:
        return random.random() * 1000

    def get_balances(self):
        return None

    def get_ticker(self, pair: str) -> dict:
        ask = random.random()
        bid = ask + random.random() / 10
        last = (ask + bid) / 2
        return {'bid': float(bid),
                'ask': float(ask),
                'last': float(last)
               }

    def get_ticker_history(self, pair: str, tick_interval: int) -> List[Dict]:
        # These sanity check are necessary because bittrex cannot keep their API stable.
        if self.sim_fail():
            raise ContentDecodingError('{message} params=({pair})'.format(
                message='Got invalid response from testdummy',
                pair=pair))
        data = dict()
        # make the time column
        data['T'] = []
        now = int(time.time()) - 200 * 300 # unix epoch
        for i in range(0,200):
            # increase in 5min steps
            data['T'].append(now * 1000000000 +
                             i * 1000000000 * 300)
        for prop in ['C', 'V', 'O', 'H', 'L', 'BV']:
            data[prop] = []
            for i in range(0,200):
                data[prop].append(random.random())
        ret = dict()
        return data

    def get_order(self, order_id: str) -> Dict:
        if self.sim_fail():
            raise OperationalException('{message} params=({order_id})'.format(
                message='cant get order',
                order_id=order_id))
        data = self._pairs[order_id] # uuid
        # data :: [pair, rate, amount, uuid]
        return {
            'id': order_id,
            'type': data[3], # LIMIT_BUY or LIMIT_SELL
            'pair': data[0], # pair
            'opened': '', # date opened
            'rate': data[1],
            'amount': data[2],
            'remaining': 0,
            'closed': 'true'
        }

    def cancel_order(self, order_id: str) -> None:
        raise OperationalException('{message} params=({order_id})'.format(
                message='cant cancel order',
                order_id=order_id))

    def get_pair_detail_url(self, pair: str) -> str:
        return None

    def get_markets(self) -> List[str]:
        return self.conf['pair_whitelist']

    def get_market_summaries(self) -> List[Dict]:
        return None

    def get_wallet_health(self) -> List[Dict]:
        return None

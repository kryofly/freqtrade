
# whitelist, blacklist, filtering, all of that will
# eventually become some rules to run on a generic ACL engine

# try to anticipate that by using some python package

import pytest

from freqtrade.main import refresh_whitelist
from freqtrade.strategy import Strategy
#from freqtrade.exchange import Exchanges
from freqtrade import exchange

from freqtrade.tests.strattest import XStrategy


def setup_teststrategy(conf):
    return XStrategy(conf)

@pytest.fixture(scope="module")
def trade_conf():
    """ Returns specialized configuration, using exchange testdummy"""
    configuration = {
        # Note: if dry_run is set to True, the exchange
        # is bypassed for buy/sell calls
        "dry_run": False,
        "stake_currency": "BTC",
        "stake_amount": 0.001,
        "exchange": {
            "name": "testdummy",
            "failrate": 0,
            "pair_whitelist": [
                "BTC_ETH",
                "BTC_TKN",
                "BTC_TRST",
                "BTC_SWT",
                "BTC_BCC"
            ],
            # Available pairs on the exchange
            "test_pairs": [
                "BTC_ETH",
                "BTC_TKN",
                "BTC_TRST",
                "BTC_SWT",
                "BTC_BCC",
                "BTC_FOO",
                "BTC_BAR"
            ]
        },
    }
    return configuration

def test_refresh_whitelist(trade_conf):
    strat = setup_teststrategy(trade_conf)
    exchange.init(trade_conf)
    whitelist = trade_conf['exchange']['pair_whitelist']
    pairslist = refresh_whitelist(strat, whitelist)
    for pair in whitelist:
        assert pair in pairslist
    for pair in pairslist:
        assert pair in whitelist

def test_refresh_empty_whitelist(trade_conf):
    strat = setup_teststrategy(trade_conf)
    exchange.init(trade_conf)
    whitelist = ['BTC_BAR']
    pairslist = refresh_whitelist(strat, whitelist)
    assert pairslist == ['BTC_BAR']


# pragma pylint: disable=missing-docstring,C0103

import pytest

from freqtrade import exchange

@pytest.fixture(scope="module")
def trade_conf():
    """ Returns specialized configuration, using exchange testdummy"""
    configuration = {
        "dry_run": True,
        "stake_currency": "BTC",
        "exchange": {
            "name": "testdummy",
            "failrate": 0,
            "pair_whitelist": [
                "BTC_ETH",
                "BTC_LTC",
                "BTC_GNO",
                "BTC_XRP"
            ],
            "test_pairs": [
                "BTC_ETH",
                "BTC_LTC",
                "BTC_GNO",
                "BTC_XRP"
            ]
        },
    }
    return configuration

def test_simple_testdummy_class(trade_conf):
    api = exchange.init(trade_conf)
    # exchange should return the api
    assert exchange._API

def test_simple_testdummy_class_kludge(trade_conf):
    # we shouldn't call the testdummy class directly
    # we only do it in this test
    api = exchange.Testdummy(trade_conf['exchange'])
    assert api

def test_simple_testdummy_sim_fail(trade_conf):
    api = exchange.Testdummy(trade_conf['exchange'])
    x = api.sim_fail()
    assert isinstance(x, bool)

def test_simple_testdummy_fee(trade_conf):
    api = exchange.Testdummy(trade_conf['exchange'])
    x = api.fee
    assert isinstance(x, float)

def test_simple_testdummy_buy(trade_conf):
    api = exchange.Testdummy(trade_conf['exchange'])
    x = api.buy("BTC_ETH", 0.1, 100)
    assert isinstance(x, str)
    # internal, dont test this really, just for understanding
    holds = api._pairs
    assert isinstance(holds, dict)


def test_simple_testdummy_sell(trade_conf):
    api = exchange.Testdummy(trade_conf['exchange'])
    x = api.buy ("BTC_ETH", 0.1, 100)
    x = api.sell("BTC_ETH", 0.1, 100)
    print('sell:', x)

# pragma pylint: disable=missing-docstring,C0103

import pytest

from freqtrade import exchange
from freqtrade import DependencyException, OperationalException

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

def test_simple_testdummy_class_kludge(trade_conf):
    # we shouldn't call the testdummy class directly
    # we only do it in this test
    api = exchange.Testdummy(trade_conf['exchange'])
    assert api

def test_simple_testdummy_class(trade_conf):
    api = exchange.init(trade_conf)
    # exchange should return the api
    isinstance(api, exchange.testdummy.Testdummy)

def test_simple_testdummy_sim_fail(trade_conf):
    api = exchange.init(trade_conf)
    x = api.sim_fail()
    assert isinstance(x, bool)

def test_simple_testdummy_fee(trade_conf):
    api = exchange.init(trade_conf)
    x = api.fee
    assert isinstance(x, float)

def test_simple_testdummy_buy(trade_conf):
    api = exchange.init(trade_conf)
    x = api.buy("BTC_ETH", 0.1, 100)
    assert isinstance(x, str)
    # internal, dont test this really, just for understanding
    holds = api._pairs
    assert isinstance(holds, dict)

def test_simple_testdummy_sell(trade_conf):
    api = exchange.init(trade_conf)
    api.buy ("BTC_ETH", 0.1, 100)
    api.sell("BTC_ETH", 0.1, 100)

def test_simple_testdummy_get_balance(trade_conf):
    api = exchange.init(trade_conf)
    n = api.get_balance('foobar')
    isinstance(n, float)

def test_simple_testdummy_get_ticker(trade_conf):
    api = exchange.init(trade_conf)
    t = api.get_ticker('foobar')
    isinstance(t, tuple)
    isinstance(t['ask'], float)
    isinstance(t['bid'], float)
    isinstance(t['last'], float)

def test_simple_testdummy_get_ticker_history(trade_conf):
    api = exchange.init(trade_conf)
    hist = api.get_ticker_history('BTC_ETH', 5)
    isinstance(hist, tuple)
    assert hist['C']
    isinstance(hist['C'], list)

def test_simple_testdummy_get_order_not_exist(trade_conf):
    api = exchange.init(trade_conf)
    # error if order UUID doesnt exist
    with pytest.raises(OperationalException, match=r'cant get order'):
        api.get_order('TEST1234')

def test_simple_testdummy_get_order(trade_conf):
    api = exchange.init(trade_conf)
    uuid = api.buy("BTC_ETH", 0.1, 100)
    t = api.get_order(uuid)
    isinstance(t, tuple)
    assert t['type'] == 'LIMIT_BUY'

def test_simple_testdummy_cancel_order(trade_conf):
    api = exchange.init(trade_conf)
    uuid = api.buy("BTC_ETH", 0.1, 100)
    with pytest.raises(OperationalException, match=r'cant cancel order'):
        api.cancel_order(uuid)

def test_simple_testdummy_get_markets(trade_conf):
    api = exchange.init(trade_conf)
    l = api.get_markets()
    isinstance(l, list)
    assert 'BTC_ETH' in l

def test_simple_testdummy_get_wallet_health(trade_conf):
    api = exchange.init(trade_conf)
    l = api.get_wallet_health()
    isinstance(l, list)
    for x in l:
        isinstance(x, tuple)
        assert x['Currency']
        assert x['IsActive']


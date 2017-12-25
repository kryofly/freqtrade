# pragma pylint: disable=missing-docstring,C0103
import copy
from unittest.mock import MagicMock

import pytest
import requests
from sqlalchemy import create_engine

from freqtrade import DependencyException, OperationalException
from freqtrade.analyze import SignalType
from freqtrade.exchange import Exchanges
from freqtrade.main import create_trade, init, \
    get_target_bid, _process
from freqtrade.misc import get_state, State
from freqtrade.persistence import Trade
from freqtrade.trade import handle_trade

from freqtrade.strategy import Strategy
from freqtrade.tests.strattest import XStrategy

from freqtrade.main import create_trade, init, get_target_bid, execute_sell
from freqtrade import exchange
from freqtrade import persistence


def setup_teststrategy():
    return XStrategy()

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
                "BTC_TKN",
                "BTC_TRST",
                "BTC_SWT",
                "BTC_BCC"
            ]
        },
    }
    return configuration

def trades_update(trades):
    # update any trades that has been placed but not executed
    for trade in trades:
        if trade.open_order_id:
            order_id = trade.open_order_id
            exchange_order = exchange.get_order(order_id)
            trade.update(exchange_order)

def trades_sell_all(trades):
    for trade in trades:
        assert trade.open_rate
        assert trade.fee
        msg = execute_sell(trade, 0.01)
        Trade.session.flush()
        # KLUDGE: this exposes how the buy/sell api
        # is not symmetrical with respect to responisibility of
        # the persistence layer. In buy, the create_trade
        # takes care of that. Here we need to call flush ourself.

def trades_buy_pairs(strategy, pairs):
    # we should succeed in entering long trades for all
    # pairs (since the strategy is buy everywhere in time,
    # and the testdummy-exchange is acting deterministic
    # with respect to failure-rate
    for i in range(0,len(pairs)):
        traded = create_trade(strategy, strategy.stake_amount())
        assert traded # we entered a trade (in this case)

def test_exchange_testdummy(trade_conf, ticker, health, mocker):
    conf = trade_conf
    strategy = setup_teststrategy()
    # FIX: create_trade needs _CONF for whitelist,
    #      the function should take config as an arg
    mocker.patch.dict('freqtrade.main._CONF', conf)

    persistence.init(conf, create_engine('sqlite://'))
    exchange.init(conf)

    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    assert not trades

    pairs = trade_conf['exchange']['pair_whitelist']

    trades_buy_pairs(strategy, pairs)

    # At this point, we should have bought up all pairs
    # listed in 'pairs' variable
    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    # assert we have entered trades in all pairs
    assert len(trades) == len(pairs)

    trades_sell_all(trades)

    trades_update(trades)

    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    assert trades == []


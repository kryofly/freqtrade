from unittest.mock import MagicMock
import pytest

from sqlalchemy import create_engine

from freqtrade.strategy import Strategy
from freqtrade.tests.strattest import XStrategy
from freqtrade.trade import handle_trade
from freqtrade.main import create_trade, init, execute_sell
from freqtrade.persistence import Trade
from freqtrade import exchange
from freqtrade import persistence
from freqtrade import OperationalException

# Test using the real exchange, but dry-run flag

def setup_strategy(config):
    return Strategy(config)

def test_handle_trade(default_conf, limit_buy_order, limit_sell_order, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=MagicMock(return_value={
                              'bid': 0.17256061,
                              'ask': 0.172661,
                              'last': 0.17256061
                          }),
                          buy=MagicMock(return_value='mocked_limit_buy'),
                          sell=MagicMock(return_value='mocked_limit_sell'))
    init(default_conf, create_engine('sqlite://'))
    create_trade(strategy, 15.0)

    trade = Trade.query.first()
    assert trade

    trade.update(limit_buy_order)
    assert trade.is_open is True

    state = handle_trade(strategy, trade)
    if state:
        current_rate = exchange.get_ticker(trade.pair)['bid']
        execute_sell(trade, current_rate)
    assert trade.open_order_id == 'mocked_limit_sell'

    # Simulate fulfilled LIMIT_SELL order for trade
    trade.update(limit_sell_order)

    assert trade.close_rate == 0.0802134
    assert trade.close_profit == 0.10046755
    assert trade.close_date is not None

# Test using the testdummy exchange, and reset dry-run flag
# FIX: alot of redundant code from test_exchange_testdummy.py
#      move into conftest.py?

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

def setup_teststrategy(conf):
    return XStrategy(conf)

def test_trade_buy_sell(trade_conf, mocker):
    conf = trade_conf
    strat = setup_teststrategy(conf)
    mocker.patch.dict('freqtrade.main._CONF', conf)
    persistence.init(conf, create_engine('sqlite://'))
    exchange.init(conf)
    traded = create_trade(strat, strat.stake_amount())
    assert traded
    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    assert trades
    for trade in trades:
        assert trade.open_rate
        assert trade.fee
        msg = execute_sell(trade, 0.01)
        Trade.session.flush()

# try to simulate a trade that has been exited out-of-band
# manually, removing the rug, so to speak
def test_trade_buy_gone_sell(trade_conf, mocker):
    conf = trade_conf
    strat = setup_teststrategy(conf)
    mocker.patch.dict('freqtrade.main._CONF', conf)
    persistence.init(conf, create_engine('sqlite://'))
    exchange.init(conf)
    traded = create_trade(strat, strat.stake_amount())
    assert traded
    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    assert trades
    # remove the pair manually by calling the exchange directly
    for trade in trades:
        assert trade.open_rate
        assert trade.fee
        order_id = trade.open_order_id
        exchange.sell(trade.pair, trade.open_rate, trade.amount)
    # sell the pair using normal freqtrade api
    for trade in trades:
        # implemented in testdummy def sell()
        with pytest.raises(OperationalException, matches=r'No such pair to sell'):
          msg = execute_sell(trade, 0.01)


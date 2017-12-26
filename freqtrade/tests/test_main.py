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
from freqtrade.strategy import Strategy
from freqtrade.trade import handle_trade

def setup_strategy(default_conf):
    s = Strategy(default_conf)
    # KLUDGE need to restore the strategy since it is used between tests
    s._config['exchange']['pair_whitelist'] = ['BTC_ETH']
    return Strategy(default_conf)

def test_process_trade_creation(default_conf, ticker, health, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          get_wallet_health=health,
                          buy=MagicMock(return_value='mocked_limit_buy'))
    whitelist = default_conf['exchange']['pair_whitelist']
    assert whitelist
    init(default_conf, create_engine('sqlite://'))

    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    assert not trades

    # KLUDGE testing a _ prefixed function
    result = _process(strategy)
    assert result is True

    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    assert len(trades) == 1
    trade = trades[0]
    assert trade is not None
    assert trade.stake_amount == strategy.stake_amount()
    assert trade.is_open
    assert trade.open_date is not None
    assert trade.exchange == Exchanges.BITTREX.name
    assert trade.open_rate == 0.072661
    assert trade.amount == 0.1376 # FIX: please review this assert!


def test_process_exchange_failures(default_conf, ticker, health, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    sleep_mock = mocker.patch('time.sleep', side_effect=lambda _: None)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          get_wallet_health=health,
                          buy=MagicMock(side_effect=requests.exceptions.RequestException))
    init(default_conf, create_engine('sqlite://'))
    result = _process(strategy)
    assert result is False
    assert sleep_mock.has_calls()


def test_process_operational_exception(default_conf, ticker, health, mocker):
    strategy = setup_strategy(default_conf)
    msg_mock = MagicMock()
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=msg_mock)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          get_wallet_health=health,
                          buy=MagicMock(side_effect=OperationalException))
    init(default_conf, create_engine('sqlite://'))
    assert get_state() == State.RUNNING

    result = _process(strategy)
    assert result is False
    assert get_state() == State.STOPPED
    assert 'OperationalException' in msg_mock.call_args_list[-1][0][0]


def test_process_trade_handling(default_conf, ticker, limit_buy_order, health, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch('freqtrade.main.get_signal',
                 side_effect=lambda *args: False if args[1] == SignalType.SELL else True)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          get_wallet_health=health,
                          buy=MagicMock(return_value='mocked_limit_buy'),
                          get_order=MagicMock(return_value=limit_buy_order))
    init(default_conf, create_engine('sqlite://'))

    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    assert not trades
    result = _process(strategy)
    assert result is True
    trades = Trade.query.filter(Trade.is_open.is_(True)).all()
    assert len(trades) == 1
    result = _process(strategy)
    assert result is False


def test_create_trade(default_conf, ticker, limit_buy_order, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          buy=MagicMock(return_value='mocked_limit_buy'))
    # Save state of current whitelist
    whitelist = copy.deepcopy(default_conf['exchange']['pair_whitelist'])

    init(default_conf, create_engine('sqlite://'))
    create_trade(strategy, 15.0)

    trade = Trade.query.first()
    assert trade is not None
    assert trade.stake_amount == 15.0
    assert trade.is_open
    assert trade.open_date is not None
    assert trade.exchange == Exchanges.BITTREX.name

    # Simulate fulfilled LIMIT_BUY order for trade
    trade.update(limit_buy_order)

    assert trade.open_rate == 0.07256061
    assert trade.amount == 206.43811673387373

    assert whitelist == default_conf['exchange']['pair_whitelist']


def test_create_trade_minimal_amount(default_conf, ticker, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    buy_mock = mocker.patch('freqtrade.main.exchange.buy', MagicMock(return_value='mocked_limit_buy'))
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker)
    init(default_conf, create_engine('sqlite://'))
    min_stake_amount = 0.0005
    create_trade(strategy, min_stake_amount)
    rate, amount = buy_mock.call_args[0][1], buy_mock.call_args[0][2]
    assert rate * amount >= (min_stake_amount - 0.00001)


def test_create_trade_no_stake_amount(default_conf, ticker, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          buy=MagicMock(return_value='mocked_limit_buy'),
                          get_balance=MagicMock(return_value=default_conf['stake_amount'] * 0.5))
    with pytest.raises(DependencyException, match=r'.*stake amount.*'):
        create_trade(strategy, default_conf['stake_amount'])


def test_create_trade_no_pairs(default_conf, ticker, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          buy=MagicMock(return_value='mocked_limit_buy'))
    with pytest.raises(DependencyException, match=r'.*No pair in whitelist.*'):
        strategy._config['exchange']['pair_whitelist'] = []
        create_trade(strategy, default_conf['stake_amount'])

def test_close_trade(default_conf, ticker, limit_buy_order, limit_sell_order, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    mocker.patch.multiple('freqtrade.rpc', init=MagicMock(), send_msg=MagicMock())
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          buy=MagicMock(return_value='mocked_limit_buy'))

    # Create trade and sell it
    init(default_conf, create_engine('sqlite://'))
    create_trade(strategy, 15.0)

    trade = Trade.query.first()
    assert trade

    trade.update(limit_buy_order)
    trade.update(limit_sell_order)
    assert trade.is_open is False

    with pytest.raises(ValueError, match=r'.*closed trade.*'):
        state = handle_trade(strategy, trade)
        if state:
            current_rate = exchange.get_ticker(trade.pair)['bid']
            main.execute_sell(trade, current_rate)

def test_balance_fully_ask_side(mocker):
    mocker.patch.dict('freqtrade.main._CONF', {'bid_strategy': {'ask_last_balance': 0.0}})
    assert get_target_bid({'ask': 20, 'last': 10}) == 20


def test_balance_fully_last_side(mocker):
    mocker.patch.dict('freqtrade.main._CONF', {'bid_strategy': {'ask_last_balance': 1.0}})
    assert get_target_bid({'ask': 20, 'last': 10}) == 10


def test_balance_bigger_last_ask(mocker):
    mocker.patch.dict('freqtrade.main._CONF', {'bid_strategy': {'ask_last_balance': 1.0}})
    assert get_target_bid({'ask': 5, 'last': 10}) == 5

# pragma pylint: disable=missing-docstring, too-many-arguments, too-many-ancestors, C0103
import re
from datetime import datetime, date
from random import randint
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from telegram import Update, Message, Chat
from telegram.error import NetworkError

from freqtrade import __version__
from freqtrade.main import init, create_trade
from freqtrade.misc import update_state, State, get_state
from freqtrade.strategy import Strategy
from freqtrade.persistence import Trade
from freqtrade.rpc import telegram
from freqtrade.rpc.telegram import authorized_only, is_enabled, send_msg, _status, _status_table, \
    _profit, _forcesell, _performance, _daily, _count, _start, _stop, _balance, _version, _help

def setup_strategy(config):
    return Strategy(config)

def test_is_enabled(default_conf, mocker):
    mocker.patch.dict('freqtrade.rpc.telegram._CONF', default_conf)
    default_conf['telegram']['enabled'] = False
    assert is_enabled() is False


def test_init_disabled(default_conf, mocker):
    mocker.patch.dict('freqtrade.rpc.telegram._CONF', default_conf)
    default_conf['telegram']['enabled'] = False
    telegram.init(default_conf)


def test_authorized_only(default_conf, mocker):
    mocker.patch.dict('freqtrade.rpc.telegram._CONF', default_conf)

    chat = Chat(0, 0)
    update = Update(randint(1, 100))
    update.message = Message(randint(1, 100), 0, datetime.utcnow(), chat)
    state = {'called': False}

    @authorized_only
    def dummy_handler(*args, **kwargs) -> None:
        state['called'] = True

    dummy_handler(MagicMock(), update)
    assert state['called'] is True


def test_authorized_only_unauthorized(default_conf, mocker):
    mocker.patch.dict('freqtrade.rpc.telegram._CONF', default_conf)

    chat = Chat(0xdeadbeef, 0)
    update = Update(randint(1, 100))
    update.message = Message(randint(1, 100), 0, datetime.utcnow(), chat)
    state = {'called': False}

    @authorized_only
    def dummy_handler(*args, **kwargs) -> None:
        state['called'] = True

    dummy_handler(MagicMock(), update)
    assert state['called'] is False


def test_authorized_only_exception(default_conf, mocker):
    mocker.patch.dict('freqtrade.rpc.telegram._CONF', default_conf)

    update = Update(randint(1, 100))
    update.message = Message(randint(1, 100), 0, datetime.utcnow(), Chat(0, 0))

    @authorized_only
    def dummy_handler(*args, **kwargs) -> None:
        raise Exception('test')

    dummy_handler(MagicMock(), update)


def test_status_handle(default_conf, update, ticker, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    msg_mock = MagicMock()
    mocker.patch('freqtrade.main.rpc.send_msg', MagicMock())
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker)
    init(default_conf, create_engine('sqlite://'))

    update_state(State.STOPPED)
    _status(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'trader is not running' in msg_mock.call_args_list[0][0][0]
    msg_mock.reset_mock()

    update_state(State.RUNNING)
    _status(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'no active trade' in msg_mock.call_args_list[0][0][0]
    msg_mock.reset_mock()

    # Create some test data
    create_trade(strategy, 15.0)
    # Trigger status while we have a fulfilled order for the open trade
    _status(bot=MagicMock(), update=update)

    assert msg_mock.call_count == 1
    assert '[BTC_ETH]' in msg_mock.call_args_list[0][0][0]


def test_status_table_handle(default_conf, update, ticker, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    msg_mock = MagicMock()
    mocker.patch('freqtrade.main.rpc.send_msg', MagicMock())
    mocker.patch.multiple(
        'freqtrade.rpc.telegram',
        _CONF=default_conf,
        init=MagicMock(),
        send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          buy=MagicMock(return_value='mocked_order_id'))
    init(default_conf, create_engine('sqlite://'))
    update_state(State.STOPPED)
    _status_table(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'trader is not running' in msg_mock.call_args_list[0][0][0]
    msg_mock.reset_mock()

    update_state(State.RUNNING)
    _status_table(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'no active order' in msg_mock.call_args_list[0][0][0]
    msg_mock.reset_mock()

    # Create some test data
    create_trade(strategy, 15.0)

    _status_table(bot=MagicMock(), update=update)

    text = re.sub('</?pre>', '', msg_mock.call_args_list[-1][0][0])
    line = text.split("\n")
    fields = re.sub('[ ]+', ' ', line[2].strip()).split(' ')

    assert int(fields[0]) == 1
    assert fields[1] == 'BTC_ETH'
    assert msg_mock.call_count == 1


def test_profit_handle(default_conf, update, ticker, limit_buy_order, limit_sell_order, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    msg_mock = MagicMock()
    mocker.patch('freqtrade.main.rpc.send_msg', MagicMock())
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker)
    init(default_conf, create_engine('sqlite://'))


    _profit(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'no closed trade' in msg_mock.call_args_list[0][0][0]
    msg_mock.reset_mock()

    # Create some test data
    create_trade(strategy, 15.0)
    trade = Trade.query.first()

    # Simulate fulfilled LIMIT_BUY order for trade
    trade.update(limit_buy_order)

    _profit(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'no closed trade' in msg_mock.call_args_list[-1][0][0]
    msg_mock.reset_mock()

    # Simulate fulfilled LIMIT_SELL order for trade
    trade.update(limit_sell_order)

    trade.close_date = datetime.utcnow()
    trade.is_open = False

    _profit(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert '*ROI:* `1.50701325 (10.05%)`' in msg_mock.call_args_list[-1][0][0]
    assert 'Best Performing:* `BTC_ETH: 10.05%`' in msg_mock.call_args_list[-1][0][0]


def test_forcesell_handle(default_conf, update, ticker, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    rpc_mock = mocker.patch('freqtrade.main.rpc.send_msg', MagicMock())
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=MagicMock())
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker)
    init(default_conf, create_engine('sqlite://'))

    from freqtrade.main import _event_log

    # Create some test data
    create_trade(strategy, 15.0)

    trade = Trade.query.first()
    assert trade

    update.message.text = '/forcesell 1'
    _forcesell(bot=MagicMock(), update=update)

    assert rpc_mock.call_count == 2
    assert 'Selling [BTC/ETH]' in rpc_mock.call_args_list[-1][0][0]
    assert '0.07256061 (profit: ~-0.64%)' in rpc_mock.call_args_list[-1][0][0]


def test_forcesell_all_handle(default_conf, update, ticker, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    rpc_mock = mocker.patch('freqtrade.main.rpc.send_msg', MagicMock())
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=MagicMock())
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker)
    init(default_conf, create_engine('sqlite://'))

    from freqtrade.main import _event_log

    # Create some test data
    for _ in range(4):
        create_trade(strategy, 15.0)
    rpc_mock.reset_mock()

    update.message.text = '/forcesell all'
    _forcesell(bot=MagicMock(), update=update)

    assert rpc_mock.call_count == 4
    for args in rpc_mock.call_args_list:
        assert '0.07256061 (profit: ~-0.64%)' in args[0][0]


def test_forcesell_handle_invalid(default_conf, update, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock())
    init(default_conf, create_engine('sqlite://'))

    # Trader is not running
    update_state(State.STOPPED)
    update.message.text = '/forcesell 1'
    _forcesell(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'not running' in msg_mock.call_args_list[0][0][0]

    # No argument
    msg_mock.reset_mock()
    update_state(State.RUNNING)
    update.message.text = '/forcesell'
    _forcesell(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'Invalid argument' in msg_mock.call_args_list[0][0][0]

    # Invalid argument
    msg_mock.reset_mock()
    update_state(State.RUNNING)
    update.message.text = '/forcesell 123456'
    _forcesell(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'Invalid argument.' in msg_mock.call_args_list[0][0][0]


def test_performance_handle(
        default_conf, update, ticker, limit_buy_order, limit_sell_order, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    msg_mock = MagicMock()
    mocker.patch('freqtrade.main.rpc.send_msg', MagicMock())
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker)
    init(default_conf, create_engine('sqlite://'))

    # Create some test data
    create_trade(strategy, 15.0)
    trade = Trade.query.first()
    assert trade

    # Simulate fulfilled LIMIT_BUY order for trade
    trade.update(limit_buy_order)

    # Simulate fulfilled LIMIT_SELL order for trade
    trade.update(limit_sell_order)

    trade.close_date = datetime.utcnow()
    trade.is_open = False

    _performance(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'Performance' in msg_mock.call_args_list[0][0][0]
    assert '<code>BTC_ETH\t10.05%</code>' in msg_mock.call_args_list[0][0][0]

def test_daily_handle(
        default_conf, update, ticker, limit_buy_order, limit_sell_order, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    msg_mock = MagicMock()
    mocker.patch('freqtrade.main.rpc.send_msg', MagicMock())
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker)
    init(default_conf, create_engine('sqlite://'))
    
    # Create some test data
    create_trade(strategy, 15.0)
    trade = Trade.query.first()
    assert trade

    # Simulate fulfilled LIMIT_BUY order for trade
    trade.update(limit_buy_order)

    # Simulate fulfilled LIMIT_SELL order for trade
    trade.update(limit_sell_order)

    trade.close_date = datetime.utcnow()
    trade.is_open = False

    #try valid data
    update.message.text = '/daily 7'
    _daily(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'Daily' in msg_mock.call_args_list[0][0][0]
    assert str(date.today()) + '  1.50701325 BTC' in msg_mock.call_args_list[0][0][0]
    
    #try invalid data
    msg_mock.reset_mock()
    update_state(State.RUNNING)
    update.message.text = '/daily -2'
    _daily(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'must be an integer greater than 0' in msg_mock.call_args_list[0][0][0]   
    
    
def test_count_handle(default_conf, update, ticker, mocker):
    strategy = setup_strategy(default_conf)
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    msg_mock = MagicMock()
    mocker.patch.multiple(
        'freqtrade.rpc.telegram',
        _CONF=default_conf,
        init=MagicMock(),
        send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock(),
                          get_ticker=ticker,
                          buy=MagicMock(return_value='mocked_order_id'))
    init(default_conf, create_engine('sqlite://'))
    update_state(State.STOPPED)
    _count(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'not running' in msg_mock.call_args_list[0][0][0]
    msg_mock.reset_mock()
    update_state(State.RUNNING)

    # Create some test data
    create_trade(strategy, 15.0)
    msg_mock.reset_mock()
    _count(bot=MagicMock(), update=update)

    msg = '<pre>  current\n---------\n        1</pre>'
    assert msg in msg_mock.call_args_list[0][0][0]


def test_performance_handle_invalid(default_conf, update, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch('freqtrade.main.get_signal', side_effect=lambda *args: True)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          validate_pairs=MagicMock())
    init(default_conf, create_engine('sqlite://'))

    # Trader is not running
    update_state(State.STOPPED)
    _performance(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert 'not running' in msg_mock.call_args_list[0][0][0]


def test_start_handle(default_conf, update, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          _CONF=default_conf,
                          init=MagicMock())
    init(default_conf, create_engine('sqlite://'))
    update_state(State.STOPPED)
    assert get_state() == State.STOPPED
    _start(bot=MagicMock(), update=update)
    assert get_state() == State.RUNNING
    assert msg_mock.call_count == 0


def test_start_handle_already_running(default_conf, update, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          _CONF=default_conf,
                          init=MagicMock())
    init(default_conf, create_engine('sqlite://'))
    update_state(State.RUNNING)
    assert get_state() == State.RUNNING
    _start(bot=MagicMock(), update=update)
    assert get_state() == State.RUNNING
    assert msg_mock.call_count == 1
    assert 'already running' in msg_mock.call_args_list[0][0][0]


def test_stop_handle(default_conf, update, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          _CONF=default_conf,
                          init=MagicMock())
    init(default_conf, create_engine('sqlite://'))
    update_state(State.RUNNING)
    assert get_state() == State.RUNNING
    _stop(bot=MagicMock(), update=update)
    assert get_state() == State.STOPPED
    assert msg_mock.call_count == 1
    assert 'Stopping trader' in msg_mock.call_args_list[0][0][0]


def test_stop_handle_already_stopped(default_conf, update, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          _CONF=default_conf,
                          init=MagicMock())
    init(default_conf, create_engine('sqlite://'))
    update_state(State.STOPPED)
    assert get_state() == State.STOPPED
    _stop(bot=MagicMock(), update=update)
    assert get_state() == State.STOPPED
    assert msg_mock.call_count == 1
    assert 'already stopped' in msg_mock.call_args_list[0][0][0]


def test_balance_handle(default_conf, update, mocker):
    mock_balance = [{
        'Currency': 'BTC',
        'Balance': 10.0,
        'Available': 12.0,
        'Pending': 0.0,
        'CryptoAddress': 'XXXX',
    }, {
        'Currency': 'ETH',
        'Balance': 0.0,
        'Available': 0.0,
        'Pending': 0.0,
        'CryptoAddress': 'XXXX',
    }]
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)
    mocker.patch.multiple('freqtrade.main.exchange',
                          get_balances=MagicMock(return_value=mock_balance))

    _balance(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert '*Currency*: BTC' in msg_mock.call_args_list[0][0][0]
    assert 'Balance' in msg_mock.call_args_list[0][0][0]


def test_help_handle(default_conf, update, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)

    _help(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert '*/help:* `This help message`' in msg_mock.call_args_list[0][0][0]


def test_version_handle(default_conf, update, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    msg_mock = MagicMock()
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock(),
                          send_msg=msg_mock)

    _version(bot=MagicMock(), update=update)
    assert msg_mock.call_count == 1
    assert '*Version:* `{}`'.format(__version__) in msg_mock.call_args_list[0][0][0]


def test_send_msg(default_conf, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock())
    bot = MagicMock()
    send_msg('test', bot)
    assert not bot.method_calls
    bot.reset_mock()

    default_conf['telegram']['enabled'] = True
    send_msg('test', bot)
    assert len(bot.method_calls) == 1


def test_send_msg_network_error(default_conf, mocker):
    mocker.patch.dict('freqtrade.main._CONF', default_conf)
    mocker.patch.multiple('freqtrade.rpc.telegram',
                          _CONF=default_conf,
                          init=MagicMock())
    default_conf['telegram']['enabled'] = True
    bot = MagicMock()
    bot.send_message = MagicMock(side_effect=NetworkError('Oh snap'))
    send_msg('test', bot)

    # Bot should've tried to send it twice
    assert len(bot.method_calls) == 2

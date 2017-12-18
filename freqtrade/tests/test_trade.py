from unittest.mock import MagicMock
import pytest

from sqlalchemy import create_engine

from freqtrade.strategy import Strategy
from freqtrade.trade import handle_trade
from freqtrade.main import create_trade, init, get_target_bid, execute_sell
from freqtrade.persistence import Trade
from freqtrade import exchange

def setup_strategy():
    return Strategy()

def test_handle_trade(default_conf, limit_buy_order, limit_sell_order, mocker):
    strategy = setup_strategy()
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

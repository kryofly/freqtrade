
import logging
from datetime import datetime
from freqtrade.strategy import Strategy
from freqtrade.persistence import Trade
from freqtrade import exchange
from freqtrade.analyze import get_signal, SignalType
from freqtrade import main

logger = logging.getLogger('freqtrade')

def min_roi_reached(strategy: Strategy, trade: Trade, current_rate: float, current_time: datetime) -> bool:
    """
    Based an earlier trade and current price and ROI configuration, decides whether bot should sell
    :return True if bot should sell at current rate
    """
    current_profit = trade.calc_profit(current_rate)
    if current_profit < strategy.stoploss():
        logger.debug('Stop loss hit.')
        return True

    # Check if time matches and current rate is above threshold
    time_diff = (current_time - trade.open_date).total_seconds() / 60
    for duration, threshold in sorted(strategy.minimal_roi().items()):
        if time_diff > float(duration) and current_profit > threshold:
            return True

    logger.debug('Threshold not reached. (cur_profit: %1.2f%%)', current_profit * 100.0)
    return False

def handle_trade(strategy: Strategy, trade: Trade) -> bool:
    """
    Sells the current pair if the threshold is reached and updates the trade record.
    :return: True if trade has been sold, False otherwise
    """
    if not trade.is_open:
        raise ValueError('attempt to handle closed trade: {}'.format(trade))

    logger.debug('Handling %s ...', trade)
    current_rate = exchange.get_ticker(trade.pair)['bid']

    # Check if minimal roi has been reached
    if not min_roi_reached(strategy, trade, current_rate, datetime.utcnow()):
        return False

    #logger.debug('Checking sell_signal ...')
    #if not get_signal(strategy, trade.pair, SignalType.SELL):
    #    return False

    main.execute_sell(trade, current_rate)
    return True

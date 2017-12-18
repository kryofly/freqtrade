
from typing import Optional, Dict
import logging
from datetime import datetime
from decimal import Decimal, getcontext

from freqtrade.strategy import Strategy
from freqtrade import exchange
from freqtrade.analyze import get_signal, SignalType
from freqtrade import main
#from freqtrade import persistence

logger = logging.getLogger('freqtrade')

def calc_profit(trade, rate: Optional[float] = None) -> float:
    """
    Calculates the profit in percentage (including fee).
    :param rate: rate to compare with (optional).
    If rate is not set trade.close_rate will be used
    :return: profit in percentage as float
    """
    getcontext().prec = 8
    return float((Decimal(rate or trade.close_rate) - Decimal(trade.open_rate))
                 / Decimal(trade.open_rate) - Decimal(trade.fee))

def min_roi_reached(strategy: Strategy, trade,
                    current_rate: float,
                    current_time: datetime) -> bool:
    """
    Based an earlier trade and current price and ROI configuration, decides whether bot should sell
    :return True if bot should sell at current rate
    """
    # get how old the trade is in unit of frames
    time_diff = ((current_time - trade.open_date).total_seconds() / 60) / strategy.tick_interval()
    current_profit = calc_profit(trade, current_rate)
    if strategy.stoploss(trade, current_rate, current_time, time_diff, current_profit):
        print('--- stoploss hit: profit=%s, rate=%s, time=%s (%s frames)'
              %(current_profit, current_rate, current_time, time_diff))
        logger.debug('Stop loss hit.')
        return True

    # Check if time matches and current rate is above threshold
    for duration, threshold in sorted(strategy.minimal_roi().items()):
        if time_diff > float(duration) and current_profit > threshold:
            print('current_profit=%s > min_roi_treshold=%s AND %s frames is > limit=%s'
                  %(current_profit, threshold, time_diff, duration))
            return True

    logger.debug('Threshold not reached. (cur_profit: %1.2f%%)', current_profit * 100.0)
    return False

def handle_trade(strategy: Strategy, trade) -> bool:
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


from typing import Optional, Dict
import logging
from datetime import datetime
from decimal import Decimal, getcontext

from freqtrade.strategy import Strategy
from freqtrade import exchange
from freqtrade.analyze import get_signal, SignalType

logger = logging.getLogger('freqtrade')

def calc_profit(trade, rate: Optional[float] = None) -> float:
    """
    Calculates the profit in percentage (including fee).
    :param rate: rate to compare with (optional).
    If rate is not set trade.close_rate will be used
    :return: profit in percentage as float
    """
    getcontext().prec = 8
    # KLUDGE/WARNING: Python is trying to accomodate everyone
    #      by treaing number zero (integer or float)
    #      as logical False. If we really have a zero-price
    #      that should override trade.close_rate
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
        #logger.info('--- stoploss hit: profit=%s, buyrate=%s rate=%s, time=%s (%s frames)'
        #            %(current_profit, trade.open_rate, current_rate, current_time, time_diff))
        return True

    # Check if time matches and current rate is above threshold
    #for duration, threshold in sorted(strategy.minimal_roi().items()):
    #    if time_diff > float(duration) and current_profit > threshold:
    #        print('current_profit=%s > min_roi_treshold=%s AND %s frames is > limit=%s'
    #              %(current_profit, threshold, time_diff, duration))
    #        return True

    #logger.info('Threshold not reached. (cur_profit: %1.2f%%) [open=%.8f cur=%.8f]', current_profit * 100.0, trade.open_rate, current_rate)
    return False

# Make this a pure function, that only returns True/False,
# Depending on wheter to exit this trade
# Returns True if we should exit this trade
def handle_trade(strategy: Strategy, trade) -> bool:
    """
    Sells the current pair if the threshold is reached and updates the trade record.
    :return: True if trade has been sold, False otherwise
    """
    if not trade.is_open:
        raise ValueError('attempt to handle closed trade: {}'.format(trade))

    logger.info('Handling %s ...', trade)
    current_rate = exchange.get_ticker(trade.pair)['bid']

    # Update statistic values for stoplosses, etc
    trade.update_stats(current_rate)
    strategy.step_frame(trade, current_rate, '')
    # FIX: above, we arent persistence with the update of trade.stat_stoploss_glide_rate
    # we need to call trade session flush here

    # Check if minimal roi has been reached
    if min_roi_reached(strategy, trade, current_rate, datetime.utcnow()):
        return True
    # FIX20171222: test needed, if we disable sell-signals tests still passes
    #logger.debug('Checking sell_signal ...')
    if get_signal(strategy, trade.pair, SignalType.SELL):
        return True

    return False

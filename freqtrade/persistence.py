import logging
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Optional, Dict

import arrow
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.pool import StaticPool

from freqtrade import trade

logger = logging.getLogger(__name__)

_CONF = {}
_DECL_BASE = declarative_base()


def init(config: dict, engine: Optional[Engine] = None) -> None:
    """
    Initializes this module with the given config,
    registers all known command handlers
    and starts polling for message updates
    :param config: config to use
    :param engine: database engine for sqlalchemy (Optional)
    :return: None
    """
    _CONF.update(config)
    if not engine:
        if _CONF.get('dry_run', False):
            # the user wants dry run to use a DB
            if _CONF.get('dry_run_db', False):
                engine = create_engine('sqlite:///tradesv3.dry_run.sqlite')
            # Otherwise dry run will store in memory
            else:
                engine = create_engine('sqlite://',
                                       connect_args={'check_same_thread': False},
                                       poolclass=StaticPool,
                                       echo=False)
        else:
            engine = create_engine('sqlite:///tradesv3.sqlite')

    session = scoped_session(sessionmaker(bind=engine, autoflush=True, autocommit=True))
    Trade.session = session()
    Trade.query = session.query_property()
    _DECL_BASE.metadata.create_all(engine)


def cleanup() -> None:
    """
    Flushes all pending operations to disk.
    :return: None
    """
    Trade.session.flush()


class Trade(_DECL_BASE):
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    exchange = Column(String, nullable=False)
    pair = Column(String, nullable=False)
    is_open = Column(Boolean, nullable=False, default=True)
    fee = Column(Float, nullable=False, default=0.0)
    open_rate = Column(Float)
    close_rate = Column(Float)
    close_profit = Column(Float)
    stake_amount = Column(Float, nullable=False)
    amount = Column(Float)
    open_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    close_date = Column(DateTime)
    open_order_id = Column(String)
    # these are specific to strategy, perhaps we can
    # add persistence object on the fly?
    stat_min_rate = Column(Float)
    stat_max_rate = Column(Float)
    stat_stoploss_glide_rate = Column(Float)

    def __repr__(self):
        return 'Trade(id={}, pair={}, amount={:.8f}, open_rate={:.8f}, open_since={})'.format(
            self.id,
            self.pair,
            self.amount,
            self.open_rate,
            arrow.get(self.open_date).humanize() if self.is_open else 'closed'
        )

    def update(self, order: Dict) -> None:
        """
        Updates this entity with amount and actual open/close rates.
        :param order: order retrieved by exchange.get_order()
        :return: None
        """
        if not order['closed']:
            return

        logger.info('Updating trade (id=%d) ...', self.id)
        if order['type'] == 'LIMIT_BUY':
            # Update open rate and actual amount
            self.open_rate = order['rate']
            self.amount = order['amount']
            logger.info('LIMIT_BUY has been fulfilled for %s.', self)
        elif order['type'] == 'LIMIT_SELL':
            # Set close rate and set actual profit
            self.close_rate = order['rate']
            self.close_profit = trade.calc_profit(self)
            self.close_date = datetime.utcnow()
            self.is_open = False
            logger.info(
                'Marking %s as closed as the trade is fulfilled and found no open orders for it.',
                self
            )
        else:
            raise ValueError('Unknown order type: {}'.format(order['type']))

        self.open_order_id = None
        if 'session' in dir(Trade):
            Trade.session.flush()

    def update_stats(self, current_rate: Dict) -> None:
        """
        Updates this entity statistics with current rates.
        :param current_rate: current rate retrieved by exchange.get_ticker()
        :return: None
        """
        #logger.info('Updating statistics for trade (id=%s) ...', self.id)
        need_update = False

        if not self.stat_min_rate or current_rate < self.stat_min_rate:
            self.stat_min_rate = current_rate
            need_update = True
        if not self.stat_max_rate or current_rate > self.stat_max_rate:
            self.stat_max_rate = current_rate
            need_update = True

        # need to always update due to self.stat_stoploss_glide_rate being updated in every frame
        need_update = True

        if need_update:
            if 'session' in dir(Trade):
                Trade.session.flush()

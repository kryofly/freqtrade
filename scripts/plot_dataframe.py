#!/usr/bin/env python3

import sys
import argparse
from typing import List

import matplotlib  # Install PYQT5 manually if you want to test this helper function
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt

from freqtrade import exchange, analyze
from freqtrade.dataframe import load_dataframe
from freqtrade.strategy import Strategy
from freqtrade.misc import parse_args_common
from freqtrade import optimize
from freqtrade.optimize.backtesting import backtest

# we could reuse misc.py:parse_args() if split up and composable
def plot_parse_args(args: List[str]):
    parser = parse_args_common(args, 'Graph utility')
    parser.add_argument(
        '-p', '--pair',
        help = 'What currency pair',
        dest = 'pair',
        default = 'BTC_XLM',
        type = str,
    )
    parser.add_argument(
        '-b', '--backtest',
        help = 'BACKTEST=yes -- Run backtest, plot buy/sell occurencies',
        default = False,
        type=bool,
    )
    return parser.parse_args(args)

def plot_analyzed_dataframe(args, strategy: Strategy, pairs: str) -> None:
    """
    Calls analyze() and plots the returned dataframe
    :param pair: pair as str
    :return: None
    """

    backtest_result = None

    if args.backtest:
        print('---- calling backtest ----')
        data = optimize.load_data(args.datadir, ticker_interval=strategy.tick_interval(), pairs=pairs)
        prepdata = optimize.preprocess(strategy, data)
        backtest_results = backtest(strategy, prepdata, 1, True)
        print('---- backtesting done ----')

    ld = load_dataframe(args.datadir, ticker_interval=5, pairs=pairs)
    d = ld[pairs[0]];
    dataframe = analyze.analyze_ticker(strategy,d)

    dataframe.loc[dataframe['buy']  == 1, 'buy_price']  = dataframe['close']
    dataframe.loc[dataframe['sell'] == 1, 'sell_price'] = dataframe['close']

    # Two subplots sharing x axis
    fig, (ax1, ax2, ax3) = plt.subplots(3, sharex=True)
    fig.suptitle(pairs, fontsize=14, fontweight='bold')
    ax1.plot(dataframe.index.values, dataframe['close'], label='close')
    #ax1.plot(dataframe.index.values, dataframe['sell'], 'ro', label='sell')
    #ax1.plot(dataframe.index.values, dataframe['sma'], '--', label='SMA')
    #ax1.plot(dataframe.index.values, dataframe['tema'], ':', label='TEMA')
    #ax1.plot(dataframe.index.values, dataframe['blower'], '-.', label='BB low')
    #ax1.plot(dataframe.index.values, dataframe['buy_price'], 'bo', label='buy')
    ax1.legend()

    # take the backtest_result and:
    # pick out the buy-sell pairs and make an accumulated profit graph
    # write that graph into dataframe['profit'] for example
    if backtest_result:
        None

    # plot the buy/sell occurencies
    ax2.plot(dataframe.index.values, dataframe['buy'], 'bo', label='Buy')
    ax2.plot(dataframe.index.values, dataframe['sell'], 'ro', label='Sell')
    ax2.legend()

    ax3.plot(dataframe.index.values, dataframe['sto_fastk'], label='k')
    ax3.plot(dataframe.index.values, dataframe['sto_fastd'], label='d')
    ax3.plot(dataframe.index.values, dataframe['rsi'], label='rsi')
    ax3.plot(dataframe.index.values, [20] * len(dataframe.index.values))
    ax3.legend()

    # Fine-tune figure; make subplots close to each other and hide x ticks for
    # all but bottom plot.
    fig.subplots_adjust(hspace=0)
    plt.setp([a.get_xticklabels() for a in fig.axes[:-1]], visible=False)
    plt.show()


if __name__ == '__main__':
    args = plot_parse_args(sys.argv[1:])
    print('---- Plotting currency pair:', args.pair)
    strategy = Strategy().load(args.strategy)
    plot_analyzed_dataframe(args, strategy, [args.pair])


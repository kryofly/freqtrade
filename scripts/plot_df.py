#!/usr/bin/env python3

import sys
import argparse
import json
import matplotlib.pyplot as plt
import numpy as np

import freqtrade.optimize as optimize
import freqtrade.misc as misc
from freqtrade.strategy import Strategy
import freqtrade.exchange as exchange
import freqtrade.analyze  as analyze


def plot_parse_args(args):
    parser = misc.parse_args_common(args, 'Graph utility')
    # FIX: perhaps delete those backtesting options that are not feasible (shows up in -h)
    misc.backtesting_options(parser)
    parser.add_argument(
        '-p', '--pair',
        help = 'Select pair to plot the indicator for.',
        dest = 'pair',
        default = None
    )
    parser.add_argument(
        '-i1', '--ind1',
        help = 'indicator 1 to plot.',
        dest = 'ind1',
        default = None
    )
    parser.add_argument(
        '-i2', '--ind2',
        help = 'indicator 2 to plot.',
        dest = 'ind2',
        default = None
    )
    return parser.parse_args(args)


def plot_indicator(strategy, args) -> None:
    """
    """

    ind1 = args.ind1
    ind2 = args.ind2
    filter_pairs = args.pair

    config = misc.load_config(args.config)
    pairs = config['exchange']['pair_whitelist']
    if pairs == []: # if there was an empty pairs_whitelist in config
        pairs = strategy.backtest_pairs()
    if filter_pairs:
        filter_pairs = filter_pairs.split(',')
        pairs = list(set(pairs) & set(filter_pairs))
        print('Filter, keep pairs %s' % pairs)

    tickers = optimize.load_data(args.datadir, pairs=pairs,
                                 ticker_interval=args.ticker_interval,
                                 )
    dataframes = optimize.preprocess(strategy, tickers)

    if not ind1 or not ind2:
        print('ERROR: Must supply indicators to plot')
        print('Following indicators are valid:')
        for pair, df in dataframes.items():
            for ind in df.keys():
                print('    ', ind)

        sys.exit()

    close = None
    arr1 = None
    arr2 = None
    max_x = 0
    for pair, df in dataframes.items():
        max_x = len(df['close'])
        close = df['close']
        arr1  = df[ind1]
        arr2  = df[ind2]

    fig, (ax1, ax2, ax3) = plt.subplots(3, sharex=True)
    fig.suptitle('total profit')
    ax1.plot(close, label='close')
    ax2.plot(arr1, label=ind1)
    ax3.plot(arr2, label=ind2)
    fig.subplots_adjust(hspace=0)
    plt.setp([a.get_xticklabels() for a in fig.axes[:-1]], visible=False)
    plt.show()


if __name__ == '__main__':
    args = plot_parse_args(sys.argv[1:])
    strategy = Strategy().load(args.strategy)
    plot_indicator(strategy, args)

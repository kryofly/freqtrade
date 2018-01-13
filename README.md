
# Get started

 $ cd freqtrade/
 # copy example config. Dont forget to insert your api keys
 $ cp config.json.example config.json
 $ python -m venv .env
 $ source .env/bin/activate
 $ pip install -r requirements.txt
 $ pip install -e .
 $ ./freqtrade/main.py


# Workflow example

   1) Download ticker data

   mkdir freqtrade/tests/testdata-20180113
   cd freqtrade/tests/testdata-20180113
   # edit pairs.json
   ./download_backtest_data.py -p pairs.json

  2) Edit your strategy.py

  vi strat-heikinashi.py

  3) Possibly run hyperopt

  freqtrade -s strat-heikinashi hyperopt --timeperiod=-100
  
  3) Run backtesting to see performance numbers
     and export plot data

  freqtrade -s strat-heikinashi backtesting --timeperiod=-200 --export=trades,results


# Plotting

## Plot profit

  python scripts/plot_profit.py -p BTC_ETH,BTC_LTC -s strat-heikinashi

## Plot an indicator

  python scripts/plot_df.py -p BTC_ETH -i1 sto_fastk -i2 rsi

  This example uses the default indicator


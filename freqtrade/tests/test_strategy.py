
import pytest

from freqtrade.strategy import Strategy

def setup_strategy(conf):
    return Strategy(conf)

@pytest.fixture(scope="module")
def conf():
    """ Returns specialized configuration, using exchange testdummy"""
    configuration = {
        # Note: if dry_run is set to True, the exchange
        # is bypassed for buy/sell calls
        "dry_run": False,
        "stake_currency": "BTC",
        "stake_amount": 0.001,
        "exchange": {
            "name": "testdummy",
            "failrate": 0,
            "pair_whitelist": ["BTC_ETH", "BTC_BCC"],
            # Available pairs on the exchange
            "test_pairs": ["BTC_ETH", "BTC_BAR"]
        }
    }
    return configuration

def test_strategy_object (conf):
    strat = setup_strategy(conf)
    isinstance(strat, Strategy)

def test_strategy_whitelist(conf):
    strat = setup_strategy(conf)
    whitelist = strat.whitelist()
    for pair in conf['exchange']['pair_whitelist']:
        assert pair in whitelist

def test_strategy_set_whitelist(conf):
    strat = setup_strategy(conf)
    new_whitelist = ['FOO', 'XYZ']
    strat.set_whitelist(new_whitelist)
    whitelist = strat.whitelist()
    # Note: the default strategy doesn't maintain its own whitelist,
    # it uses the one found in  exchange pair_whitelist,
    # therefor when we set the whitelist above, we dont
    # set a deepcopy, instead we identity, so we in effect
    # also change the config, as seen in this for loop:
    #for pair in new_whitelist:
    for pair in conf['exchange']['pair_whitelist']:
        assert pair in whitelist

def test_strategy_load(conf):
    strat = setup_strategy(conf)
    newstrat = strat.load('strat-heikinashi')
    assert strat.name() == 'default'
    assert newstrat.name() == 'heikin-ashi'
    
def test_strategy_indicators(conf):
    strat = setup_strategy(conf)
    inds = strat.select_indicators(None)
    assert len(inds) > 0
    isinstance(inds, list)
    for ind in inds:
        isinstance(ind, list)

def test_strategy_misc(conf):
    strat = setup_strategy(conf)
    isinstance(strat.stake_amount(), float)
    assert strat.max_open_trades() > 0
    assert strat.tick_interval()   > 0
    assert strat.ask_last_balance() == 0
    ticker = {'ask': 10, 'bid': 8, 'last': 9}
    assert strat.get_target_bid(ticker)

#!/usr/bin/env python3
"""Entry point for one scheduled trading cycle.

Run this from cron, a systemd timer, or a GitHub Actions workflow. It performs
exactly one pass and exits — no long-lived process to wedge or leak.

    */5 * * * * cd /path/to/tradebot && ./run.py --symbols XAUUSD >> logs/bot.log 2>&1

Everything defaults to paper trading. Going live needs both ``--mode live`` on
the command line and ``TRADEBOT_ALLOW_LIVE=yes`` in the environment.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

from tradebot.brokers.base import TradingMode
from tradebot.brokers.paper import PaperBroker
from tradebot.news.calendar import EconomicCalendar, NewsDetector
from tradebot.risk.journal import TradeJournal
from tradebot.risk.limits import RiskLimits, RiskManager, RiskState
from tradebot.runtime.cycle import TradingCycle
from tradebot.runtime.lock import AlreadyRunning, InstanceLock
from tradebot.runtime.state import StateStore
from tradebot.runtime.watchdog import Heartbeat
from tradebot.portfolio.manager import PortfolioManager
from tradebot.strategy.base import NoOpStrategy
from tradebot.strategy.stack import StrategyStack
from tradebot.strategy.mamba import MambaBreakout
from tradebot.strategy.mamba_all import MambaAll
from tradebot.strategy.mamba_both import MambaBoth
from tradebot.strategy.mamba_channel import MambaChannel
from tradebot.strategy.mamba_fib import MambaFib
from tradebot.strategy.mamba_ny import MambaNY
from tradebot.strategy.mamba_retest import MambaRetest
from tradebot.strategy.mamba_signals import MambaSignals
from tradebot.strategy.mamba_rsi import MambaRsi
from tradebot.strategy.reversion import RsiScalper
from tradebot.strategy.runner import BigRunner
from tradebot.strategy.trend import BreakoutRider, KamaTrend

log = logging.getLogger("tradebot")

# Every strategy the bot knows how to run. Adding one here makes it available
# to --strategies; the portfolio manager decides whether it may actually trade.
REGISTRY = {
    # The best thing measured on this project: gold 15m, profitable in 4 of 4
    # walk-forward stretches, and the drawdown stays inside AquaFunded's 6%
    # loss cap (measured from the starting balance, confirmed with Leo).
    # See FINDINGS.md.
    "gold_scalper": lambda: RsiScalper(
        oversold=35, overbought=65, reward=1.5, trend_ema=200
    ),
    # The pickier variant. Half the money, but half the drawdown too -- the
    # one to fall back to if the firm ever measures loss from the peak
    # instead, because that would disqualify gold_scalper.
    "gold_safe": lambda: RsiScalper(
        oversold=30, overbought=70, reward=1.5, trend_ema=200
    ),
    # Bot 2: MambaFX's breakout, as he teaches it for small accounts --
    # intrabar entry the moment the zone breaks, stop at half the breakout
    # candle, 1:8 target. US30 on 15m bars.
    #
    # Aggression belongs in the SIZE, not the trade count. Loosening the
    # touch filter to 2 and allowing four trades a session takes 250 trades
    # instead of 51 and earns LESS at every risk level while doubling the
    # drawdown -- profit factor falls 1.70 to 1.17. The extra trades are
    # marginal ones his own filter exists to refuse. Pushing risk instead
    # runs +1,030/month against +553 with half the pain.
    "mamba": lambda: MambaBreakout(
        wait_for_close=False, stop_candle_frac=0.5, reward=8.0
    ),
    # Risk lives on the command line (--risk-per-trade), and for this strategy
    # it peaks at 5-6% on every account size tested from $150 to $2,635.
    # Ten months of US30 15m at 6%: 5.2x, about +17.8% a month compounding,
    # with a 36% peak-to-trough dip on the way. Past 6% the account compounds
    # through deeper holes and ends smaller -- 15% risk returns 1.5x.
    # All three sessions. Twice the trades for slightly more money and a
    # meaningfully worse profit factor -- worth having, not worth defaulting.
    "mamba_all_sessions": lambda: MambaBreakout(
        wait_for_close=False, stop_candle_frac=0.5, reward=8.0,
        sessions=("tokyo", "london", "newyork"),
    ),
    # His OTHER trade, from a live breakdown: find a channel the market is
    # honouring on a higher timeframe, wait for price to reach one edge and be
    # rejected there, take it back toward the far side. Fires about 1.2 times
    # a day against the breakout's 0.17, because a respected channel gets
    # touched far more often than a level gets broken -- which is what closes
    # the gap to his stated two-to-three trades a day.
    #
    # Wants ~2% risk, not the breakout's 6%: more trades at a 15% win rate
    # means longer losing runs, and 6% turns a 39% drawdown into 83%.
    "mamba_channel": lambda: MambaChannel(target_pct=1.0),
    # Both his trades in one bot, which is how he actually trades: breakout
    # when a level gives way, channel fade when it holds. 4.59x over ten
    # months of US30 15m at 2% risk on 1.08 trades a day, up in three quarters
    # of four -- better than either half alone. Wants ~2% risk; 6% returns
    # 7.63x but through a 90% drawdown and only two quarters up.
    # THE BUILD. Both his trades, plus his two-timeframe rule applied where it
    # actually bites -- the fade. 9.69x over ten months of US30 15m at 5% risk,
    # profitable in four quarters of four, drawdown 47% against 86% without the
    # filter. See research/mamba_notes.md.
    # Bot 2. No hold cap, and that is a measured decision rather than an
    # omission. Capping the hold was briefly registered at 180 minutes on the
    # strength of an 11.93x result, which turned out to be an artifact: the cap
    # sat below the session gate in MambaBreakout.evaluate, so it only ever
    # fired during New York hours and trades ran as long as 1425 minutes. With
    # the check moved above the gate and actually enforcing itself, every cap
    # is far worse than none -- 30 min 1.12x, 1 hr 2.46x, 2 hr 2.48x, 3 hr
    # 0.97x, none 11.05x -- because the 1:8 winners need hours to arrive and
    # cutting them off keeps all the losses and discards the payoff. His own
    # words agree: "I don't care what anybody says about holding trades for a
    # few hours or 8 hours or whatever."
    #
    # The cost is frequency: 0.52 trades a day, because one position per symbol
    # plus a ~10 hour hold blocks everything else. That is a real tension with
    # wanting 2-3 a day and it is not solved yet.
    # His actual small-account method, from the one video built for a $100
    # account: break a level, wait for the retest, sell the rejection. Entry on
    # the retest rather than the break, stop just past the level, target the
    # nearest opposing structure (~1:3), and his own stated risk ceiling of
    # "three to five percent max".
    # His New York session break, built to his words with nothing of mine in it.
    # Every value traces to a sentence: two touches ("resistance and support
    # lines do not need to be perfect"), 1:3 ("a nice little one to three"),
    # 13:30-17:00 UTC ("I don't like to trade much past 10:00 a.m."), 35-minute
    # hold ("30 minutes, 35 minutes at the most"), max 3 a day, stop past the
    # structure ("stops are right above the highs"), breakeven ("might even put
    # my stop losses to break-even here"), half off ("I'm gonna take half my
    # profits here"), doubling up ("we're doubling up on that position"), and
    # skipping trades into strong opposing structure ("we're at a pretty strong
    # resistance here. So, no, not the smartest trade").
    #
    # NAS100 5m, 3.5 months, 3% risk: 0.33x on 1.96 trades a day.
    "mamba_ny": lambda: MambaNY(
        add_at=1.0, breakeven_at=1.0, scale_at=1.5, block_into_structure=0.8,
    ),
    # The same trade with only the entry and exit rules, no management. 0.61x on
    # 2.50 trades a day -- inside the two-to-three he states.
    "mamba_ny_plain": lambda: MambaNY(),
    # "We have that other fair value gap now supporting price" -- with the stop
    # placed behind the gap. Best NY variant measured: US30 5m 3% gives 1.18x on
    # 2.46 trades a day, against 1.12x without it.
    "mamba_ny_gap": lambda: MambaNY(use_fair_value_gap=True),
    # His SMALL-ACCOUNT FLIP, which is Leo's actual situation. Different numbers
    # from his normal trade, and both sets are his:
    #   "when I want to flip a small account, I have to go for higher and higher
    #    risk rewards... We have a fat one to seven, one to 10 risk to reward."
    #   "we're risking $5, which is 25% of the account"
    #   "I don't mind going and risking 15% on the next trade."
    #   "It's very important that you use a 5-minute or 1-minute chart simply
    #    because we are super scalping."
    #   "I drew up my resistance, I drew up my support, and I drew my trend line...
    #    we're getting in as soon as this trend line or the support zone breaks."
    #   "The biggest key here, we're waiting for volume to come in."
    # Risk lives on the command line; he names 10-25% for this mode.
    # US30 5m, 3.5 months: 0.72x on 1.11 trades a day. NAS100: 0.64x on 0.47.
    # His three-confirmation setup, the most precisely specified thing he
    # teaches -- he builds it on screen from a blank chart and reads out every
    # setting: "the upper band needs to be 75 and the lower band needs to be 25
    # okay inputs are going to stay 14", "we're going to change the inputs to 34"
    # for the Bollinger bands. Then direction, then a drawn level, then the band
    # break. Stop "Above This Little Resistance where these Wicks have gone",
    # take profit one, stop to breakeven, take profit two.
    #
    # 15m, 10 months, 5%: US30 0.92x, XAUUSD 1.10x, GBPUSD 1.03x on 0.01-0.02
    # trades a day. With the RSI band relaxed: US30 0.58x on 2.04 a day.
    "mamba_rsi": lambda: MambaRsi(),
    "mamba_rsi_loose": lambda: MambaRsi(require_rsi=False),
    "mamba_flip": lambda: MambaNY(
        reward=7.0, trendline_bars=24, volume_mult=1.3,
    ),
    # ALL his setups, meant to be run across ALL his markets at once, because
    # that is how he actually trades. His watchlist is on screen -- gold, LTC,
    # FIL, BTC, ETH, XRP, NAS100, US30 -- and he says "i'm actually going to be
    # full time trading just nasdaq us 30 gbp usd and all of my cryptos". He is
    # never flat for a week, let alone the 71 idle days a single-market build
    # produces.
    #
    # Run it with: --strategies mamba_all --symbols XAUUSD,US30,NAS100,GBPUSD
    #
    # Gold, US30, NAS100 and GBPUSD together, 10 months: 2.55 trades a day,
    # active on 211 of 222 trading days -- his frequency and his coverage. Money
    # at 2% risk: 0.35x.
    # His Fibonacci "gold zone" -- his most-used tool, in 14 videos and 36
    # statements, and he trades exactly two levels out of the whole toolkit:
    # "the fibonacci is just a zero point five or six one eight zone that's the
    # only zones I want to see get rejected". Drawn across one impulse push,
    # "from this low to this high", refusing wicks that are "not really set as
    # that push". Entry is the retracement being rejected inside 0.5-0.618.
    #
    # 15m, 10 months, 3%: US30 0.39x on 0.34/day, NAS100 0.82x on 0.47/day,
    # GBPUSD 0.77x on 0.08/day, gold no trades.
    # His Fibonacci gold zone, paired with the double top the way he pairs them:
    # "you see a double top like why is this your entry check this out you're
    # gonna take... my Fibonacci... look at this beautiful 50 and a 6-1-8
    # rejection". US30 15m 3%: 1.05x on 0.15/day against 0.40x for the fib alone.
    "mamba_fib": lambda: MambaFib(require_double=True),
    "mamba_fib_alone": lambda: MambaFib(),
    # THE PATTERNS DECIDE THE TRADE. An M means sell, a bullish engulfing means
    # buy, a swept high means sell, divergence means the move ends, a gap under
    # price holds it up. Each one points a way and he trades when they agree --
    # "that's two confirmations if not like six".
    #
    # US30 5m 3%: 0.80x on 2.64 trades a day at 48% winners; needing four to
    # agree gives 0.91x on 0.23 a day.
    # =====================================================================
    # THE BUILD. His patterns decide the trade, on his whole watchlist, in his
    # session, at his frequency.
    #
    # Run it with:
    #   --strategies mamba_signals \
    #   --symbols XAUUSD,US30,NAS100,GBPUSD,BTCUSD,ETHUSD,LTCUSD,XRPUSD
    #
    # His watchlist is read off his own screen -- XAU, LTC, FIL, BTC, ETH, XRP,
    # NAS100, US30 -- plus "nasdaq us 30 gbp usd and all of my cryptos".
    #
    # Ten months, 2% risk, all eight markets:
    #   1.21x, 2.98 trades a day, active on 302 of 304 days, 47.1% winners,
    #   worst drop 27%.
    #
    # The session filter earns its place even with crypto in the mix, which was
    # not obvious: trading round the clock instead of only his New York window
    # takes 1.21x down to 0.52x and doubles the drawdown. His "I don't like to
    # trade much past 10:00 a.m." holds on markets that never close.
    # =====================================================================
    "mamba_signals": lambda: MambaSignals(min_votes=2),
    # Two a day instead of three: 1.11x, 1.99 a day, 47.2% winners, 24% drop.
    "mamba_signals_2": lambda: MambaSignals(min_votes=2, max_trades_per_day=2),
    # How he gets out of bad trades without paying for them. "I ended up closing
    # around this area um just because I wasn't sure if price was going to fully
    # reverse" / "trend got broke... it's not going to come back". Plus his own
    # breakeven trigger, "we got to a 1 to two stops can go to break even" -- two
    # R, not the one R every earlier test here used.
    #
    # Ten months, 2%, eight markets: 1.22x with full stops on 6.0% of trades
    # against 6.7% without.
    "mamba_signals_noloss": lambda: MambaSignals(
        min_votes=2, breakeven_at=2.0, breakeven_pad=0.1, scale_at=2.0,
        exit_on_reason_gone=True,
    ),
    # Round the clock, for reference. Worse on both counts.
    "mamba_signals_247": lambda: MambaSignals(min_votes=2, session=""),
    # UK100 is on his screen and tradable on the account, so it is available as a
    # ninth market. FRA40 is also on his screen but the broker does not offer it.
    # Nine markets: 0.89x on 2.96 a day against 1.21x on eight.
    #   --symbols XAUUSD,US30,NAS100,GBPUSD,BTCUSD,ETHUSD,LTCUSD,XRPUSD,UK100
    # His stated ORDER, which is direction first from the higher timeframes and
    # patterns confirming inside it: "first off i need to determine are we going
    # up are we going down are we in a bullish trend or a bearish trend... and
    # that's going to be from the daily and the four hour". He prefers the H4 --
    # "always h4 you can use the daily as well i like the h4" -- so the H4 gates
    # and the daily can only veto.
    #
    # Ten months, 2%, all eight markets: H4 gating gives 0.76x on 2.98 a day
    # against 1.21x ungated; H4 and daily both gating gives 0.62x.
    "mamba_signals_h4": lambda: MambaSignals(min_votes=2, h4_bars=16),
    "mamba_signals_h4_daily": lambda: MambaSignals(
        min_votes=2, h4_bars=16, daily_bars=96
    ),
    # On his 1-minute chart -- "It's very important that you use a 5-minute or
    # 1-minute chart simply because we are super scalping." 45 days of 1m bars at
    # 2%: BTC 1.04x on 2.75 a day, LTC 0.92x, ETH 0.97x, US30 0.78x.
    # All three of his sessions -- "6 in one for London session and then for Asia
    # session, 10 in one". Ten months, 2%: London+NY 0.62x, all three 0.52x,
    # against 1.21x for New York alone.
    "mamba_signals_all_sessions": lambda: MambaSignals(
        min_votes=2, sessions=("tokyo", "london", "newyork")
    ),
    # His intrabar trigger -- "As soon as it breaks, we're not waiting for candle
    # to close, we're not waiting for no other confirmation."
    "mamba_signals_intrabar": lambda: MambaSignals(
        min_votes=2, wait_for_close=False
    ),
    "mamba_signals_1m": lambda: MambaSignals(
        min_votes=2, max_hold_minutes=35, stop_bars=20
    ),
    "mamba_fib": lambda: MambaFib(),
    "mamba_all": lambda: MambaAll(),
    "mamba_retest": lambda: MambaRetest(
        # "as we start to trade below our 50 moving average" -- the one indicator
        # he names out loud. Helps slightly: 2.13x against 2.06x, drop 62% vs 66%.
        ma_period=50,
        # "i'm going to trail my stop-loss all the way up." He never says how far,
        # so the distance is mine to choose, and choosing it tight contradicts the
        # rest of the same sentence -- "very tight stop loss HUGE take profit".
        # A 1R trail converts his 2.7R average winner into 1.3R. At 6R the trail
        # sits beyond every target he draws, so it only ever manages a trade that
        # has already run past its zone, which is the case he is describing.
        trail_after=6.0,
        # He says "h4 OR daily" must agree, so this belongs on. It is off because
        # I do not yet know HOW he reads the daily -- my stand-in (position within
        # a 384-bar range) is my invention, not his, and it costs 2.13x -> 1.06x.
        # Not a veto on him; a gap in what I have watched. Needs a video where the
        # daily is on screen.
        daily_tf_bars=0,
    ),
    "mamba_both": lambda: MambaBoth(
        breakout=MambaBreakout(
            wait_for_close=False, stop_candle_frac=0.5, reward=8.0
        ),
        channel=MambaChannel(target_pct=1.0, higher_tf_bars=32),
    ),
    "big_runner": BigRunner,
    "breakout_rider": BreakoutRider,
    "kama_trend": KamaTrend,
}


def build_roster(names: list[str]):
    """Instantiate the requested strategies, rejecting unknown names loudly."""
    roster = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        if name not in REGISTRY:
            raise SystemExit(
                f"unknown strategy {name!r}; known: {', '.join(sorted(REGISTRY))}"
            )
        roster.append(REGISTRY[name]())
    return roster


def load_env(path: str = ".env") -> dict:
    """Credentials from .env, or the environment when there is no file.

    The environment is what CI provides -- a GitHub Actions runner has no .env
    and never should, since committing one would publish the password. Reading
    both means the same command works on a laptop and in the cloud with no
    branching.
    """
    values: dict[str, str] = {
        key: os.environ[key]
        for key in ("TRADELOCKER_USERNAME", "TRADELOCKER_PASSWORD",
                    "TRADELOCKER_SERVER", "TRADELOCKER_ACCOUNT")
        if os.environ.get(key)
    }

    env_path = Path(path)
    if not env_path.exists():
        return values
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Quotes get pasted in out of habit and would otherwise become part of
        # the password, producing a login failure that looks like a typo.
        values[key.strip()] = value.strip().strip("'\"")
    return values


def build_broker(args):
    """Construct the requested adapter. Paper is the default everywhere."""
    mode = TradingMode(args.mode)

    if args.broker == "paper":
        broker = PaperBroker(starting_balance=args.balance, mode=TradingMode.PAPER)
        broker.connect()
        # A simulator needs a price before it can quote anything.
        for symbol in args.symbols:
            broker.set_price(symbol, args.seed_price)
        return broker

    if args.broker == "tradelocker":
        from tradebot.brokers.tradelocker import TradeLockerBroker

        # Command-line arguments win, but the .env file is the normal source.
        # Passing a password as an argument would put it in `ps` output and in
        # shell history, and a scheduled job's arguments are readable by
        # anything on the machine.
        env = load_env()
        return TradeLockerBroker(
            username=args.username or env.get("TRADELOCKER_USERNAME", ""),
            password=args.password or env.get("TRADELOCKER_PASSWORD", ""),
            server=args.server or env.get("TRADELOCKER_SERVER", ""),
            account_id=args.account or env.get("TRADELOCKER_ACCOUNT", ""),
            mode=mode,
        )

    if args.broker == "mt5":
        from tradebot.brokers.mt5 import MT5Broker

        return MT5Broker(
            login=int(args.account or 0), password=args.password,
            server=args.server, mode=mode,
        )

    raise SystemExit(f"unknown broker {args.broker!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one trading cycle.")
    parser.add_argument("--broker", default="paper",
                        choices=["paper", "tradelocker", "mt5"])
    parser.add_argument("--mode", default="paper",
                        choices=["paper", "demo", "live"],
                        help="live also requires TRADEBOT_ALLOW_LIVE=yes")
    parser.add_argument("--symbols", nargs="+", default=["XAUUSD"])
    parser.add_argument("--account", default="")
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--server", default="")
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--seed-price", type=float, default=2000.0,
                        help="paper broker only: starting price")
    parser.add_argument("--risk-per-trade", type=float, default=0.01)
    parser.add_argument("--daily-loss-limit", type=float, default=0.03)
    parser.add_argument("--max-drawdown-limit", type=float, default=0.06)
    parser.add_argument("--news-url", default="",
                        help="economic calendar JSON endpoint")
    parser.add_argument("--data-dir", default="run")
    parser.add_argument("--strategies", default="breakout_rider,kama_trend",
                        help="comma-separated; 'none' disables trading entirely")
    parser.add_argument("--review-window", type=int, default=14,
                        help="days of history each strategy is scored on")
    parser.add_argument("--review-min-trades", type=int, default=10,
                        help="trades needed before a strategy can be benched")
    parser.add_argument("--report", action="store_true",
                        help="print the portfolio report card and exit")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    strategy_names = [] if args.strategies.strip().lower() == "none" \
        else args.strategies.split(",")

    def make_manager():
        return PortfolioManager(
            roster=build_roster(strategy_names),
            journal=TradeJournal(data_dir / "journal.jsonl",
                                 starting_balance=args.balance),
            state_path=data_dir / "portfolio.json",
            window_days=args.review_window,
            min_trades=args.review_min_trades,
        )

    # Read-only view of how each strategy is doing. Deliberately available
    # without touching the broker or the lock, so it can be run any time.
    if args.report:
        if not strategy_names:
            print("no strategies configured")
            return 0
        manager = make_manager()
        review = manager.review()
        print(review.summary())
        print(review.table())
        return 0

    # Refuse to start if another copy is mid-cycle. Skipping this run is
    # always safer than double-trading the same account.
    try:
        lock = InstanceLock(data_dir / "bot.lock").acquire()
    except AlreadyRunning as err:
        log.warning("%s", err)
        return 0

    try:
        state_store = StateStore(data_dir / "risk_state.json")
        loaded = state_store.load()
        if loaded.recovered:
            log.warning("risk state was corrupt; recovered to defaults "
                        "(bad file kept at %s)", loaded.backup_path)
        risk_state = RiskState.from_dict(loaded.data)

        # The opening balance, for the stateless drawdown floor. An env var
        # rather than a flag because the value belongs with the credentials:
        # it describes the account, not the invocation, and it must be present
        # on a host that wipes the filesystem between runs -- which is exactly
        # where the stateful breakers lose their memory and this floor becomes
        # the only drawdown guard still standing.
        floor = 0.0
        raw_floor = os.environ.get("TRADEBOT_START_BALANCE", "").strip()
        if raw_floor:
            try:
                floor = float(raw_floor)
            except ValueError:
                log.warning("TRADEBOT_START_BALANCE %r is not a number; "
                            "the stateless floor is OFF this run", raw_floor)

        limits = RiskLimits(
            risk_per_trade=args.risk_per_trade,
            daily_loss_limit=args.daily_loss_limit,
            max_drawdown_limit=args.max_drawdown_limit,
            floor_balance=floor,
        )
        risk = RiskManager(limits, risk_state)

        news = None
        if args.news_url:
            calendar = EconomicCalendar(data_dir / "calendar.json")
            try:
                count = calendar.refresh_from_url(args.news_url)
                log.info("calendar loaded: %d events", count)
            except Exception as err:  # noqa: BLE001 - never block trading on news
                log.warning("calendar unavailable (%s); continuing without it", err)
            news = NewsDetector(calendar)

        broker = build_broker(args)
        journal = TradeJournal(data_dir / "journal.jsonl", starting_balance=args.balance)

        if strategy_names:
            manager = make_manager()
            # Score and bench *before* trading, so a strategy that went cold
            # cannot open one more position on the way out.
            manager.review()
            strategy = StrategyStack(manager)
            log.info("active: %s",
                     ", ".join(s.name for s in manager.active_strategies()) or "none")
        else:
            strategy = NoOpStrategy()
            log.info("no strategies configured; running without trading")

        cycle = TradingCycle(
            broker=broker,
            strategy=strategy,
            risk=risk,
            journal=journal,
            symbols=[s.upper() for s in args.symbols],
            news=news,
        )

        report = cycle.run_once()
        state_store.save(risk.state.to_dict())
        Heartbeat(data_dir / "heartbeat.json").beat(ok=report.ok, note=report.summary())

        if report.halted:
            log.warning("RISK HALT active: %s", report.halt_reason)
        for err in report.errors:
            log.error("cycle error: %s", err)

        return 0 if report.ok else 1
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())

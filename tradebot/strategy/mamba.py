"""MambaFX's session-open breakout, as he teaches it.

Extracted from his own words and charts (see research/mamba_notes.md):

    "Drew resistance, drew support, wait for a break. The rest will always be
    history. It's very simple."

The method in full:

* **Nasdaq and US30 only.** "I'm not going to look at gold. I'm not going to
  look at XRP. I'm only trading Nasdaq and US30 every single day."
* **Mark up at 6:20 Pacific, trade the 6:30 volume** -- the New York open.
  "Be prepared, because when volume comes at 6:30 every single morning, that
  trade comes like this. You have to be fast."
* Look at only the last few hours. "I don't give a f*** about" yesterday or
  the previous session.
* **A level counts only at three or four touches.** "Three or four touches,
  that's enough for me." Nine touches is "a f***ing resistance". This is the
  rule that decides whether a level is tradable at all.
* Price breaks above resistance, buy. Breaks below support, sell.
* Stop tucked just past the far side of the zone that broke -- visible on his
  chart as a thin band under the level, which is what makes the next rule
  affordable.
* **Target 1:3 minimum, 1:5 maximum.** "A simple one-to-three max -- one to
  three minimum I should say, one to five max."
* **Fakeouts are absorbed, never predicted.** "You don't detect fakeouts. If
  it fakes out and you lose, it comes back, breaks again, we re-enter. You
  take the second breakout. You take the third."
* **Two trades a day, three if he's feeling it.** A hard ceiling, not a mood.
* Then stop. Win or lose, the session is over. "A win and a loss is the same
  exact thing throughout the entire day."

Where a machine differs from him, and why each difference is defensible:

* **It never misses the open.** His whole method hinges on being at the desk
  at 6:20 Pacific every single morning -- "wake up at 6, get some coffee,
  splash cold water on your face". The bot is simply there, every day, without
  the alarm clock.
* **It cannot be scared out of a valid break.** He spends half the tutorial
  talking traders out of fearing fakeouts, because humans hesitate and miss
  the entry. A rule either fires or it doesn't.
* **It cannot revenge-trade.** The per-session cap is a hard number, so the
  "walk out of my office" discipline is structural rather than emotional.
* **Other sessions are available but off by default.** He trades New York
  only, and the touch-and-break logic is not New York-specific, so Tokyo and
  London can be switched on -- but as a tested variation, never as an
  assumption about what he does.

What is deliberately NOT copied: his 5% risk example. That is his illustration
of *not over-risking* on a $100 account, and on a real balance it is a fast
way to halve the account. Risk comes from the account's own limits instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from ..brokers.base import Candle, OrderSide
from .base import Action, AdjustStop, Enter, Strategy, StrategyContext

# Session opens in UTC. Tokyo 09:00 JST, London 08:00 UK, New York 09:30 ET --
# the hours the wider market actually turns over, which is when a range built
# beforehand gets tested.
SESSION_OPENS_UTC = {
    "tokyo": time(0, 0),
    "london": time(7, 0),
    "newyork": time(13, 30),
}


@dataclass(frozen=True)
class Zone:
    """A support or resistance band, as he draws them: a range, not a line."""

    low: float
    high: float

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0


class MambaBreakout(Strategy):
    """Break of a pre-session range, with a 1:5 bracket.

    Args:
        lookback_minutes: How much history builds the range. He looks back "a
            few hours" and explicitly refuses to look further.
        zone_pct: Thickness of each zone as a fraction of the range, so a
            level is a band rather than a knife-edge price.
        reward: Reward-to-risk multiple. His number is 5.
        stop_buffer_pct: How far past the zone the stop sits, as a fraction of
            the range. Small on purpose -- the tight stop is what makes 1:5
            reachable at all.
        min_touches: How many times price must have respected a level before
            it counts as one. His filter, and the one that decides whether a
            level is tradable at all: "three or four touches, that's enough
            for me."
        touch_tolerance: How close a bar must come to the level to count as a
            touch, as a fraction of the zone thickness.
        max_trades_per_session: "Two trades per day max. Sometimes three if
            I'm really feeling it." Also what lets a fakeout be re-entered:
            "you take the second breakout, you take the third."
        window_minutes: How long after the open a break still counts. The
            move he trades is the session opening, not the whole day.
    """

    name = "mamba_breakout"
    # 15-minute bars. He names the 5, the 15 and sometimes the 1 -- and
    # testing all three across ten months found the 15 is the only one that
    # makes money. On 1m the same rules lose thousands a month: the zones are
    # noise, the breaks are noise, and a quarter-candle stop is often smaller
    # than a single tick.
    timeframe = "15m"
    # Enough bars to always contain the pre-session window plus the trading
    # window, at any timeframe this runs on. Sized for the coarsest case: on
    # 15m bars a 3-hour range plus a 2-hour window is only 20 bars, but the
    # backtest hands the strategy exactly `lookback` bars ending at "now", and
    # if that slice starts after the session opened the range is empty and the
    # strategy silently never trades. That produced a clean sweep of zeros
    # across both 15m tables -- a bug wearing the costume of a result.
    lookback = 1500

    def __init__(
        self,
        lookback_minutes: int = 180,
        zone_pct: float = 0.05,
        reward: float = 5.0,
        stop_buffer_pct: float = 0.02,
        wait_for_close: bool = True,
        stop_candle_frac: float = 0.0,
        min_stop_ticks: float = 3.0,
        breakeven_at: float = 0.0,
        max_trades_per_session: int = 2,
        window_minutes: int = 120,
        min_touches: int = 3,
        touch_tolerance: float = 0.15,
        sessions: tuple[str, ...] = ("newyork",),
    ) -> None:
        self.lookback_minutes = lookback_minutes
        self.zone_pct = zone_pct
        self.reward = reward
        self.stop_buffer_pct = stop_buffer_pct
        # His small-account variant enters the instant price crosses the zone
        # instead of waiting for the candle to close: "we're not waiting for
        # candle closure... as soon as that resistance breaks, we are entering
        # because we're going to prioritize having a very tight stop-loss and
        # going for massive risk-to-rewards."
        self.wait_for_close = wait_for_close
        # And the stop is sized off the breakout candle rather than the zone:
        # "very tight stop loss, we'll just do about a quarter of what the
        # candle's worth." A real example he shows is 13 points against a 105
        # point target.
        self.stop_candle_frac = stop_candle_frac
        # A quarter of a one-minute candle can be a fraction of a tick, which
        # the sizing layer rightly refuses. His own example -- a 13-point stop
        # -- implies candles around 50 points tall, which is a 5m or 15m bar,
        # not a 1m one. So the candle fraction gets a floor rather than being
        # allowed to propose a stop the market cannot express.
        self.min_stop_ticks = min_stop_ticks
        # He manages winners rather than only waiting for the target: "we can
        # take half our profit, put stops to break even", "75% of my profit and
        # let the rest run". Expressed here as the multiple of risk at which
        # the stop is pulled to entry -- once a trade is that far ahead it can
        # no longer become a loss, which is what lets a 1:8 runner be held
        # without fear.
        #
        # Off by default, because measuring it says the fear was the point:
        # 1,030/month becomes 765 at 5% risk, with drawdown rising 34% to 39%.
        # It saves the small losses and kills the runners that dip before they
        # fly -- and at 1:8 the runners are the entire business. Worse on both
        # axes at every level tested (1R through 4R).
        self.breakeven_at = breakeven_at
        self.min_touches = min_touches
        self.touch_tolerance = touch_tolerance
        self.max_trades_per_session = max_trades_per_session
        self.window_minutes = window_minutes
        self.sessions = sessions

    # -- session bookkeeping ---------------------------------------------

    def _active_session(self, now: datetime) -> tuple[str, datetime] | None:
        """Which session is inside its trading window, and when it opened."""
        stamp = now.astimezone(timezone.utc)
        for name in self.sessions:
            opens = SESSION_OPENS_UTC[name]
            open_at = stamp.replace(hour=opens.hour, minute=opens.minute,
                                    second=0, microsecond=0)
            # A session that opened before midnight is still the live one in
            # the small hours; check yesterday's instance too.
            for candidate in (open_at, open_at - timedelta(days=1)):
                if 0 <= (stamp - candidate).total_seconds() / 60 <= self.window_minutes:
                    return name, candidate
        return None

    def _zones(self, candles: list[Candle], open_at: datetime) -> tuple[Zone, Zone] | None:
        """The support and resistance bands built from pre-session hours only.

        Bars at or after the open are excluded deliberately: a range that
        includes the breakout it is meant to predict cannot be broken.
        """
        start = open_at - timedelta(minutes=self.lookback_minutes)
        window = [c for c in candles if start <= c.timestamp < open_at]
        # Ten bars is enough to define a range and count touches against it.
        # The old floor of 20 was written for 1-minute bars and silently
        # blocked every 15-minute run: a 3-hour window is 180 one-minute bars
        # but only 12 fifteen-minute ones, so the strategy returned no zones,
        # took no trades, and reported a clean table of zeros that looked
        # exactly like an honest negative result.
        if len(window) < 10:
            return None

        top = max(c.high for c in window)
        bottom = min(c.low for c in window)
        span = top - bottom
        if span <= 0:
            return None

        thickness = span * self.zone_pct
        support = Zone(bottom, bottom + thickness)
        resistance = Zone(top - thickness, top)

        # His filter: a level nobody respected is not a level. Counted as bars
        # whose low reached into the support band (or high into resistance),
        # which is what "touches" means on his chart -- the wicks that stopped
        # there. Without this the bot trades the edge of any random range.
        reach = thickness * (1 + self.touch_tolerance)
        support_touches = sum(1 for c in window if c.low <= support.low + reach)
        resistance_touches = sum(1 for c in window if c.high >= resistance.high - reach)
        if support_touches < self.min_touches:
            support = None
        if resistance_touches < self.min_touches:
            resistance = None
        if support is None and resistance is None:
            return None
        return (support, resistance)

    def _trades_this_session(self, context: StrategyContext, open_at: datetime) -> int:
        return sum(
            1 for p in context.open_positions
            if p.comment == self.name and p.opened_at >= open_at
        )

    # -- the rules -------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < 60:
            return []

        active = self._active_session(context.now)
        if active is None:
            return []
        _, open_at = active

        # Move the stop to breakeven once the trade is far enough ahead. This
        # runs before the has-position return, because managing a live winner
        # is the one thing worth doing while holding.
        if self.breakeven_at > 0:
            moves: list[Action] = []
            for pos in context.open_positions:
                if pos.comment != self.name or pos.stop_loss is None:
                    continue
                risk = abs(pos.entry_price - pos.stop_loss)
                if risk <= 0:
                    continue
                ahead = ((context.bid - pos.entry_price) if pos.is_long
                         else (pos.entry_price - context.ask))
                already_safe = ((pos.stop_loss >= pos.entry_price) if pos.is_long
                                else (pos.stop_loss <= pos.entry_price))
                if ahead >= risk * self.breakeven_at and not already_safe:
                    moves.append(AdjustStop(ticket=pos.ticket,
                                            stop_loss=pos.entry_price))
            if moves:
                return moves

        # One position at a time; the risk layer enforces this too, but the
        # strategy should not be asking for what it cannot have.
        if context.has_position:
            return []
        if self._trades_this_session(context, open_at) >= self.max_trades_per_session:
            return []
        if context.news is not None and context.news.active:
            return []

        zones = self._zones(candles, open_at)
        if zones is None:
            return []
        support, resistance = zones

        bar = candles[-1]
        # The span uses whichever zones survived the touch filter.
        highs = [z.high for z in (support, resistance) if z]
        lows = [z.low for z in (support, resistance) if z]
        span = max(highs) - min(lows)
        if span <= 0:
            return []
        buffer = span * self.stop_buffer_pct

        # A break is a CLOSE beyond the zone, not a wick through it. He waits
        # for the candle: a wick that pokes out and closes back inside is the
        # move failing, not starting.
        broke_up = (bar.close > resistance.high if self.wait_for_close
                    else bar.high > resistance.high) if resistance else False
        broke_down = (bar.close < support.low if self.wait_for_close
                      else bar.low < support.low) if support else False

        # Entering intrabar means filling at the level, not at the close.
        entry_up = bar.close if self.wait_for_close else resistance.high if resistance else bar.close
        entry_down = bar.close if self.wait_for_close else support.low if support else bar.close
        candle = bar.high - bar.low

        floor = context.instrument.tick_size * self.min_stop_ticks

        if resistance and broke_up:
            if self.stop_candle_frac > 0 and candle > 0:
                stop = entry_up - max(candle * self.stop_candle_frac, floor)
            else:
                stop = resistance.low - buffer
            risk = entry_up - stop
            if risk > 0:
                return [Enter(
                    side=OrderSide.BUY,
                    stop_loss=stop,
                    take_profit=entry_up + self.reward * risk,
                    comment=self.name,
                )]

        if support and broke_down:
            if self.stop_candle_frac > 0 and candle > 0:
                stop = entry_down + max(candle * self.stop_candle_frac, floor)
            else:
                stop = support.high + buffer
            risk = stop - entry_down
            if risk > 0:
                return [Enter(
                    side=OrderSide.SELL,
                    stop_loss=stop,
                    take_profit=entry_down - self.reward * risk,
                    comment=self.name,
                )]

        return []

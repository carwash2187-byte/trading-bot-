"""MambaFX's small-account method: break a level, then trade its retest.

From "$100 Forex Account TRADING STRATEGY | EASY" (I_33XcywuIo), which is the
one video in his catalogue built explicitly for an account this size. Watched
frame by frame; every rule below is something he says or draws, and where it
disagrees with what tested better, his version is what is implemented.

His sequence, in order:

1. "first thing you're gonna do is pretty much turn the higher time frame so
   right here I'm looking at the four hours I'm gonna mark up a zone... price
   has made large rejections to the upside"
2. "price has actually came back retested it with a wick once we saw this wick
   that's when we'd start looking for sales"
3. "we're not gonna look for sales on the for our because you know obviously
   we're using a hundred dollar count we can't really trade the for our because
   you know our stop losses are gonna be too high"
4. "so now what are we gonna do it's going a 15-minute time frame"
5. "price broke below these loaves came back and as you can see retested it" --
   "this is pretty much just like a break and retest strategy"
6. "we get in a short position off that wig"
7. "stop-loss just in the middle or just above this little support zone because
   if it breaks above this support so we don't even want to be into anyways"
8. "I would target this zone... cuz it's the closest and you see a major wick
   rejection"

The distinction that matters most, and the one this file exists for: **the entry
is the retest, not the break.** The existing MambaBreakout enters as the level
gives way. He does not. He lets it break, waits for price to come back to the
level it just broke, and enters when that level rejects price from the other
side. A support that breaks becomes resistance; he sells the retest of it.

That single change is also why this can reach his stated two-to-three trades a
day. A break happens once per level. The retest of a broken level is a second,
separate, later event -- and unlike the break it can be waited for, which means
it can be caught reliably rather than chased.

On reward: he quotes "22 pips stop-loss with a 50 80 take profit" and "16 pips
stop-loss 51 pivot a profit", and the risk/reward boxes drawn on his screen
measure about 17 against 52. So roughly **1:3**, arrived at by targeting the
nearest opposing structure rather than by multiplying the stop. This file
targets structure first and falls back to a multiple only when no structure is
in range, because that is the order he does it in.

On risk he is explicit: "we don't want to risk more than you know three to five
percent max". That is a sizing decision made in run.py, not here, but it is
recorded because it is the number from the man himself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta, timezone

from ..brokers.base import Candle, OrderSide
from .mamba import SESSION_OPENS_UTC
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext


@dataclass(frozen=True)
class Level:
    """A price level price has respected, and which side it was broken from."""

    price: float
    touches: int
    broken_down: bool  # True: was support, broke downward, now resistance


class MambaRetest(Strategy):
    """Break and retest, the way he teaches it for a small account.

    Args:
        higher_tf_bars: Bars making up the "four hour" view whose rejection sets
            the direction. 96 fifteen-minute bars is 24 hours.
        level_lookback: How far back to hunt for the level that gets broken.
        zone_pct: Half-height of a level's zone, as a fraction of price. He draws
            levels as boxes, not lines -- "stop-loss just in the middle or just
            above this little support zone" only means something if the level has
            height.
        min_touches: Touches needed before he trusts a level. He counts wicks
            aloud on the chart before drawing anything.
        retest_bars: How long after a break the retest still counts. A level
            revisited weeks later is not the same trade.
        stop_zone_frac: Where in the zone the stop sits, as a fraction of zone
            height beyond the far edge. His words allow either the middle or just
            past it; this puts it just past, which is the version he draws.
        fallback_reward: Reward multiple used only when no opposing structure is
            within range. His drawn trades come out near 1:3.
        max_trades_per_day: "two, three when I like it."
    """

    name = "mamba_retest"
    timeframe = "15m"
    lookback = 500

    def __init__(
        self,
        higher_tf_bars: int = 96,
        level_lookback: int = 200,
        zone_pct: float = 0.0004,
        min_touches: int = 2,
        retest_bars: int = 24,
        stop_zone_frac: float = 0.5,
        fallback_reward: float = 3.0,
        max_trades_per_day: int = 3,
        ma_period: int = 50,
        daily_tf_bars: int = 0,
        trail_after: float = 0.0,
        sessions: tuple[str, ...] = ("newyork",),
        window_minutes: int = 210,
        breakeven_at: float = 0.0,
        scale_at: float = 0.0,
        max_hold_minutes: int = 0,
    ) -> None:
        self.higher_tf_bars = higher_tf_bars
        self.level_lookback = level_lookback
        self.zone_pct = zone_pct
        self.min_touches = min_touches
        self.retest_bars = retest_bars
        self.stop_zone_frac = stop_zone_frac
        self.fallback_reward = fallback_reward
        self.max_trades_per_day = max_trades_per_day
        # "as we start to trade below our 50 moving average we could see
        # potentially all cryptos across the board continue to drop" -- the first
        # indicator he names out loud. Cycle 1 saw SMAs 8/50/100/.../600 sitting
        # on his chart and deliberately did not build them, because building an
        # indicator he never mentions is inventing. Naming it clears that bar.
        # Zero disables.
        self.ma_period = ma_period
        # "we cannot take these five-minute trades if our h4 OR our daily is not
        # in confluence telling us we're going down." Two higher timeframes, not
        # one. Measured in 15m bars: 384 is four days, roughly a daily view.
        self.daily_tf_bars = daily_tf_bars
        # "i'm going to trail my stop-loss all the way up." Expressed in R: once
        # a trade is this far ahead, the stop follows it at that distance behind.
        # Zero disables.
        self.trail_after = trail_after
        # "The first thing being is you only trade during New York session."
        # "you trade during New York session open, which is around 6:20, 6:30 a.m."
        # 6:30 Pacific is 9:30 Eastern is 13:30 UTC, which is the newyork open
        # already in SESSION_OPENS_UTC. He makes one exception -- "New York
        # session's okay, but Tokyo session for me is better for gold."
        self.sessions = sessions
        # "It's already almost 10:00 a.m. I don't like to trade much past 10:00
        # a.m." 6:30 to 10:00 Pacific is 13:30 to 17:00 UTC -- 210 minutes. Every
        # width I tested before this (240, 390, 480, 600) was my own guess.
        self.window_minutes = window_minutes
        # "might even put my stop losses to break-even here just to be safe"
        # Measured in R.
        self.breakeven_at = breakeven_at
        # "I'm gonna secure profit still I'm gonna take half my profits here"
        # Measured in R. Both of these cost money when I tested them earlier in
        # the project; they are here because he says he does them.
        self.scale_at = scale_at
        # "You don't hold trades for a long time. You get in, you get out, and you
        # move on." He narrates a live trade at "30 minutes, 35 minutes at the
        # most". Zero disables.
        self.max_hold_minutes = max_hold_minutes

    # -- reading the chart the way he reads it ---------------------------

    def _higher_tf_bias(self, candles: list[Candle]) -> int:
        """-1 down, +1 up, 0 no opinion.

        "price has made large rejections to the upside... we already know that on
        the four-hour we should be dropping so now we can go on the smaller
        charts and look for beautiful entries." The rejection he points at is
        price reaching the top of its higher-timeframe range and failing there,
        so bias is read from where price sits in that range.
        """
        if len(candles) < self.higher_tf_bars:
            return 0
        htf = candles[-self.higher_tf_bars:]
        high = max(c.high for c in htf)
        low = min(c.low for c in htf)
        if high <= low:
            return 0
        pos = (candles[-1].close - low) / (high - low)
        if pos > 0.66:
            return -1  # up at resistance, he looks for sells
        if pos < 0.34:
            return 1
        return 0

    def _in_session(self, now) -> bool:
        """Is this inside one of his sessions? No sessions configured = always."""
        if not self.sessions:
            return True
        utc = now.astimezone(timezone.utc)
        for name in self.sessions:
            open_at = SESSION_OPENS_UTC.get(name)
            if open_at is None:
                continue
            start = utc.replace(hour=open_at.hour, minute=open_at.minute,
                                second=0, microsecond=0)
            if start <= utc <= start + timedelta(minutes=self.window_minutes):
                return True
        return False

    def _ma_bias(self, candles: list[Candle]) -> int:
        """Which side of his 50 moving average price is on. 0 when disabled."""
        if self.ma_period <= 0 or len(candles) < self.ma_period:
            return 0
        ma = sum(c.close for c in candles[-self.ma_period:]) / self.ma_period
        close = candles[-1].close
        if close < ma:
            return -1
        if close > ma:
            return 1
        return 0

    def _broken_levels(self, candles: list[Candle]) -> list[Level]:
        """Levels that were respected, then broken, recently enough to retest."""
        window = candles[-self.level_lookback:]
        if len(window) < 40:
            return []

        price = window[-1].close
        zone = price * self.zone_pct
        out: list[Level] = []

        # Walk candidate swing levels. A swing low that later gets closed
        # through is a support that became resistance -- his sell setup.
        for i in range(10, len(window) - self.retest_bars - 1):
            bar = window[i]

            is_swing_low = all(
                bar.low <= window[j].low for j in range(i - 5, i + 6) if j != i
            )
            is_swing_high = all(
                bar.high >= window[j].high for j in range(i - 5, i + 6) if j != i
            )
            if not (is_swing_low or is_swing_high):
                continue

            level = bar.low if is_swing_low else bar.high
            touches = sum(
                1 for c in window[max(0, i - 20):i + 20]
                if abs((c.low if is_swing_low else c.high) - level) <= zone
            )
            if touches < self.min_touches:
                continue

            # Did price later close clean through it, and how long ago?
            after = window[i + 1:]
            broke_at = None
            for k, c in enumerate(after):
                if is_swing_low and c.close < level - zone:
                    broke_at = k
                    break
                if is_swing_high and c.close > level + zone:
                    broke_at = k
                    break
            if broke_at is None:
                continue
            # Still inside the retest window? A level broken long ago is stale.
            if len(after) - broke_at > self.retest_bars:
                continue

            out.append(Level(price=level, touches=touches, broken_down=is_swing_low))

        return out

    def _nearest_target(
        self, candles: list[Candle], entry: float, short: bool
    ) -> float | None:
        """The closest opposing structure, which is what he actually targets.

        "I would target this zone right or this sound but I would stick from now
        to this zone cuz it's the closest and you see a major wick rejection."
        """
        window = candles[-self.level_lookback:]
        zone = entry * self.zone_pct
        best: float | None = None
        for i in range(5, len(window) - 5):
            bar = window[i]
            if short:
                if not all(bar.low <= window[j].low for j in range(i - 5, i + 6) if j != i):
                    continue
                if bar.low >= entry - zone * 4:
                    continue  # must be meaningfully below us
                if best is None or bar.low > best:
                    best = bar.low  # closest below
            else:
                if not all(bar.high >= window[j].high for j in range(i - 5, i + 6) if j != i):
                    continue
                if bar.high <= entry + zone * 4:
                    continue
                if best is None or bar.high < best:
                    best = bar.high
        return best

    def _trades_today(self, context: StrategyContext) -> int:
        """How many trades this strategy has opened today.

        Read from the risk layer, not from open positions. Counting open
        positions makes "max N trades a day" mean "max N at once", because a
        closed trade disappears from the list -- which let 4.4 trades a day
        through a cap of 3.
        """
        return context.risk.trades_today(self.name)

    # -- the rules -------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < self.higher_tf_bars + 20:
            return []
        # Managing an open trade happens before any entry gate. Everything in
        # this block would silently never run if it sat below the session check,
        # which is exactly how the hold cap broke earlier in this project.

        # "You don't hold trades for a long time. You get in, you get out."
        if self.max_hold_minutes > 0:
            for pos in context.open_positions:
                if pos.comment != self.name:
                    continue
                held = (context.now - pos.opened_at).total_seconds() / 60
                if held >= self.max_hold_minutes:
                    return [Exit(ticket=pos.ticket, reason="time-exit")]

        # "might even put my stop losses to break-even here just to be safe"
        if self.breakeven_at > 0:
            for pos in context.open_positions:
                if pos.comment != self.name or pos.stop_loss is None:
                    continue
                risk = abs(pos.entry_price - pos.stop_loss)
                if risk <= 0:
                    continue
                price = context.bid if pos.is_long else context.ask
                ahead = (price - pos.entry_price) if pos.is_long else (pos.entry_price - price)
                if ahead < risk * self.breakeven_at:
                    continue
                at_be = (pos.stop_loss >= pos.entry_price if pos.is_long
                         else pos.stop_loss <= pos.entry_price)
                if not at_be:
                    return [AdjustStop(ticket=pos.ticket, stop_loss=pos.entry_price,
                                       take_profit=pos.take_profit)]

        # "I'm gonna secure profit still I'm gonna take half my profits here"
        if self.scale_at > 0:
            for pos in context.open_positions:
                if pos.comment != self.name or pos.stop_loss is None:
                    continue
                risk = abs(pos.entry_price - pos.stop_loss)
                if risk <= 0:
                    continue
                price = context.bid if pos.is_long else context.ask
                ahead = (price - pos.entry_price) if pos.is_long else (pos.entry_price - price)
                if ahead < risk * self.scale_at:
                    continue
                # Half off, once. Whether it has already happened is inferred
                # from the stop having been pushed past entry by the breakeven
                # rule above, so no state has to survive a process restart.
                half = round(pos.lots / 2, 2)
                if half >= 0.01 and pos.lots > 0.01:
                    return [Exit(ticket=pos.ticket, lots=half, reason="half-off")]

        # "i'm going to trail my stop-loss all the way up." Managing an open
        # trade comes before deciding whether to open another one, and before
        # any entry gate -- a gate that returns early would silently disable
        # this, which is exactly how the hold cap broke.
        if self.trail_after > 0:
            for pos in context.open_positions:
                if pos.comment != self.name or pos.stop_loss is None:
                    continue
                risk = abs(pos.entry_price - pos.stop_loss)
                if risk <= 0:
                    continue
                price = context.bid if pos.is_long else context.ask
                ahead = (price - pos.entry_price) if pos.is_long else (pos.entry_price - price)
                if ahead < risk * self.trail_after:
                    continue
                want = (price - risk) if pos.is_long else (price + risk)
                better = want > pos.stop_loss if pos.is_long else want < pos.stop_loss
                if better:
                    return [AdjustStop(ticket=pos.ticket, stop_loss=want,
                                       take_profit=pos.take_profit)]

        if context.has_position:
            return []
        if self._trades_today(context) >= self.max_trades_per_day:
            return []
        if context.news is not None and context.news.active:
            return []

        # "you only trade during New York session"
        if not self._in_session(context.now):
            return []

        bias = self._higher_tf_bias(candles)
        if bias == 0:
            return []

        # Both higher timeframes have to agree. "if our h4 OR our daily is not
        # in confluence" -- either one dissenting kills the trade.
        if self.daily_tf_bars > 0 and len(candles) > self.daily_tf_bars:
            daily = candles[-self.daily_tf_bars:]
            hi = max(c.high for c in daily)
            lo = min(c.low for c in daily)
            if hi > lo:
                pos = (candles[-1].close - lo) / (hi - lo)
                daily_bias = -1 if pos > 0.66 else (1 if pos < 0.34 else 0)
                if daily_bias != bias:
                    return []

        # "as we start to trade below our 50 moving average" -- the MA has to be
        # on the same side as the trade.
        ma = self._ma_bias(candles)
        if ma != 0 and ma != bias:
            return []

        bar = candles[-1]
        zone = bar.close * self.zone_pct
        stop_room = zone * (1.0 + self.stop_zone_frac)

        for level in self._broken_levels(candles):
            # A support broken downward is now resistance: sell its retest.
            # Only if the higher timeframe agrees, which is his whole point.
            if level.broken_down and bias < 0:
                # "we get in a short position off that wig" -- the bar must
                # REACH back up into the zone and close back below it. A close
                # above means the level did not hold and there is no trade.
                if not (bar.high >= level.price - zone and bar.close < level.price):
                    continue
                stop = level.price + stop_room
                risk = stop - bar.close
                if risk <= 0:
                    continue
                target = self._nearest_target(candles, bar.close, short=True)
                if target is None or target >= bar.close - risk:
                    target = bar.close - risk * self.fallback_reward
                return [Enter(
                    side=OrderSide.SELL,
                    stop_loss=stop,
                    take_profit=target,
                    comment=self.name,
                )]

            # A resistance broken upward is now support: buy its retest.
            if (not level.broken_down) and bias > 0:
                if not (bar.low <= level.price + zone and bar.close > level.price):
                    continue
                stop = level.price - stop_room
                risk = bar.close - stop
                if risk <= 0:
                    continue
                target = self._nearest_target(candles, bar.close, short=False)
                if target is None or target <= bar.close + risk:
                    target = bar.close + risk * self.fallback_reward
                return [Enter(
                    side=OrderSide.BUY,
                    stop_loss=stop,
                    take_profit=target,
                    comment=self.name,
                )]

        return []

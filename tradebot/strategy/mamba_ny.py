"""MambaFX's New York session break — the trade he does every morning.

From "How I Make 20% Gains Daily Trading Futures" (-VdyJZlCG1M), where he
narrates one live from entry to exit with a clock running. This is his bread and
butter, and it is a different trade from the two already built: not the break-and-
retest of `mamba_retest`, not the channel fade of `mamba_channel`.

He states the whole thing in four sentences:

    "The first thing being is you only trade during New York session. Okay? you
    trade during New York session open, which is around 6:20, 6:30 a.m. Just like
    I say with indices, it does the same thing during the same time."

    "there's only two things we're looking for. We're looking for a break of a
    support or a break of resistance, but we also want to pair that with which
    way is the market moving currently."

    "If price can break past that wick again, I'm going to take a buy position.
    100% going to take a buy position. Okay, we can go for a nice little one to
    three."

    "You know, you get in, you get out, you move on. You don't hold trades for a
    long time. You get in, you get out, and you move on."

Every number below is his:

* **Session** 6:30 a.m. to 10:00 a.m. his time. "It's already almost 10:00 a.m.
  I don't like to trade much past 10:00 a.m." 6:30 Pacific is 13:30 UTC, so the
  window is 13:30-17:00 UTC, 210 minutes.
* **Timeframe** the 5 minute. "we have support on the 5 minute chart... Now, all
  we had to do go to the 1 minute if you want to."
* **Touches** two is plenty. "you got a couple touches in here, touches up here,
  touches down here. It's not perfect. Resistance and support lines do not need
  to be perfect."
* **Direction** must agree. "we see price is bullish. We're breaking out of
  previous lows... That tells me we're probably going to want to look for buys."
* **Stop** past the structure to the left. "Obviously, stops are right above the
  highs." "My stop loss is going to go below the low... the low right here to the
  left."
* **Target** 1:3, sometimes further. "we can go for a nice little one to three."
  "Got about a 1 to three. Could have gotten a little more."
* **Hold** about half an hour. "we've been trading for currently 30 minutes, 35
  minutes at the most."
* **He refuses trades into strong opposing structure.** "It's a pretty good
  position though, but we're at a pretty strong resistance here. So, no, not the
  smartest trade."

What is deliberately NOT here: the 1:8 target, the half-of-the-breakout-candle
stop, and the three-touch filter that `mamba.py` uses. Those are mine, invented
before I had watched him say otherwise. He says two touches, a structural stop,
and 1:3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..data.ohlc import timeframe_minutes
from ..brokers.base import Candle, OrderSide
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext
from .mamba import SESSION_OPENS_UTC
from .mamba_patterns import engulfing, fair_value_gap, liquidity_sweep


@dataclass(frozen=True)
class Zone:
    """A support or resistance he would actually draw, plus the swing behind it."""

    price: float
    touches: int
    is_resistance: bool
    structure: float  # the swing high/low to the LEFT, where his stop goes


class MambaNY(Strategy):
    """Break a level during the New York morning, in the market's direction.

    Args:
        session: Which open to trade from. "you only trade during New York
            session"; he makes one exception, "Tokyo session for me is better for
            gold".
        window_minutes: 210, being 6:30 a.m. to 10:00 a.m.
        zone_lookback: Bars searched for the level to break. 72 five-minute bars
            is six hours, so the level comes from before the session as well as
            during it -- he arrives at 6:30 with levels already marked.
        zone_pct: Half-height of a level, as a fraction of price. He draws boxes,
            and says outright they need not be exact.
        min_touches: 2. "a couple touches... it's not perfect."
        (trend_bars deleted -- his direction timeframe is the H4 and always was:
        "we're gonna start on the h4, ALWAYS h4, you can use the daily as well, i
        like the h4." Four hours is 240 minutes, so the bar count is 240 divided
        by the bar length. Arithmetic, not a parameter. The old 96 and 48 were
        mine and neither of them was four hours.)
        reward: 3.0. "a nice little one to three."
        max_hold_minutes: 35. "30 minutes, 35 minutes at the most."
        max_trades_per_day: 3.
        breakeven_at: R at which the stop goes to entry. "might even put my stop
            losses to break-even here just to be safe." Zero disables.
        scale_at: R at which half comes off. "I'm gonna take half my profits
            here." Zero disables.
        block_into_structure: Refuse a trade whose target is beyond opposing
            structure closer than this fraction of the target distance. "we're at
            a pretty strong resistance here. So, no, not the smartest trade."
    """

    name = "mamba_ny"
    timeframe = "5m"
    lookback = 400

    def __init__(
        self,
        session: str = "newyork",
        window_minutes: int = 210,
        zone_lookback: int = 72,
        zone_pct: float = 0.0004,
        min_touches: int = 2,
        trend_bars: int = 0,
        reward: float = 3.0,
        max_hold_minutes: int = 35,
        max_trades_per_day: int = 2,
        breakeven_at: float = 0.0,
        scale_at: float = 0.0,
        block_into_structure: float = 0.0,
        add_at: float = 0.0,
        max_adds: int = 1,
        max_losses_per_day: int = 2,
        trendline_bars: int = 0,
        volume_leads_session: bool = False,
        skip_fridays: bool = True,
        use_engulfing: bool = False,
        use_liquidity_sweep: bool = False,
        use_fair_value_gap: bool = False,
    ) -> None:
        self.session = session
        self.window_minutes = window_minutes
        self.zone_lookback = zone_lookback
        self.zone_pct = zone_pct
        self.min_touches = min_touches
        self.trend_bars = (trend_bars if trend_bars > 0
                           else 240 // max(1, timeframe_minutes(self.timeframe)))
        self.reward = reward
        self.max_hold_minutes = max_hold_minutes
        self.max_trades_per_day = max_trades_per_day
        self.breakeven_at = breakeven_at
        self.scale_at = scale_at
        self.block_into_structure = block_into_structure
        # "well let me do two yep there it is we're doubling up on that position
        # by the way I'm pretty confident we're going to push out here."
        # He adds when the trade is already working. Measured in R: once a
        # position is this far ahead, double it. Zero disables.
        self.add_at = add_at
        self.max_adds = max_adds
        # "If the second one doesn't work out, we are done for the day and we
        # come back tomorrow and we do it again." Two losers ends his day.
        self.max_losses_per_day = max_losses_per_day
        # "I pretty much drew up my resistance, I drew up my support, and I drew
        # my trend line." / "we're getting in as soon as this trend line or the
        # support zone breaks." He draws one every session and names its break as
        # a trigger in its own right. Bars used to fit it. Zero disables.
        self.trendline_bars = trendline_bars
        # "we're waiting for volume to come in" / "we do them early in the
        # morning, right at session open when there's a LOT of volume."
        #
        # He never says how much volume, so there is no multiple to set. What he
        # actually did is measurable: on the NAS100 trade in "$5,000 in 3 WEEKS"
        # the entry candle carries THE TALLEST VOLUME BAR OF THE WHOLE SESSION.
        # That is his rule -- not a threshold I picked, a superlative read off
        # his own screen. The old volume_mult=1.3 was mine and is deleted.
        self.volume_leads_session = volume_leads_session
        # "I don't like to trade Fridays cuz I like to have three days off...
        # Psychology." A refusal is a rule, so his week is Monday to Thursday.
        self.skip_fridays = skip_fridays
        # "we saw this candle here closed not only a ginormous bullish engulfing
        # candle but it closed above the tops of those rejections" -- the
        # engulfing candle IS the trigger at the level, not a filter on it.
        self.use_engulfing = use_engulfing
        # "our entry came from this 4-hour liquidity sweep" -- a trigger of its
        # own, so it is checked like the trendline break rather than as an extra
        # condition on a zone.
        self.use_liquidity_sweep = use_liquidity_sweep
        # "We have that other fair value gap now supporting price." A gap below
        # price supports a buy; a gap above resists a sell, so the stop can sit
        # behind it.
        self.use_fair_value_gap = use_fair_value_gap

    # -- reading his chart -----------------------------------------------

    def _session_window(self, now: datetime) -> tuple[datetime, datetime] | None:
        open_at = SESSION_OPENS_UTC.get(self.session)
        if open_at is None:
            return None
        utc = now.astimezone(timezone.utc)
        start = utc.replace(hour=open_at.hour, minute=open_at.minute,
                            second=0, microsecond=0)
        return start, start + timedelta(minutes=self.window_minutes)

    def _direction(self, candles: list[Candle]) -> int:
        """"which way is the market moving currently" -- -1 down, +1 up, 0 flat.

        He reads it off the chart as breaking out of previous lows or highs:
        "we see price is bullish. We're breaking out of previous lows, or you
        could say previous consolidation period."
        """
        if len(candles) < self.trend_bars:
            return 0
        window = candles[-self.trend_bars:]
        first = window[: len(window) // 2]
        last = window[len(window) // 2:]
        # Higher highs and higher lows against the earlier half is his "bullish".
        up = (max(c.high for c in last) > max(c.high for c in first)
              and min(c.low for c in last) > min(c.low for c in first))
        down = (min(c.low for c in last) < min(c.low for c in first)
                and max(c.high for c in last) < max(c.high for c in first))
        if up and not down:
            return 1
        if down and not up:
            return -1
        return 0

    def _zones(self, candles: list[Candle]) -> list[Zone]:
        """Levels with a couple of touches, and the swing behind each one."""
        window = candles[-self.zone_lookback:]
        if len(window) < 20:
            return []
        zone = window[-1].close * self.zone_pct
        out: list[Zone] = []

        for i in range(4, len(window) - 4):
            bar = window[i]
            hi_swing = all(bar.high >= window[j].high
                           for j in range(i - 4, i + 5) if j != i)
            lo_swing = all(bar.low <= window[j].low
                           for j in range(i - 4, i + 5) if j != i)
            if not (hi_swing or lo_swing):
                continue

            level = bar.high if hi_swing else bar.low
            touches = sum(
                1 for c in window
                if abs((c.high if hi_swing else c.low) - level) <= zone
            )
            if touches < self.min_touches:
                continue

            # "stops are right above the highs" / "below the low right here to
            # the left" -- the extreme of the structure this level belongs to.
            left = window[max(0, i - 8):i + 1]
            structure = (max(c.high for c in left) if hi_swing
                         else min(c.low for c in left))
            out.append(Zone(price=level, touches=touches,
                            is_resistance=hi_swing, structure=structure))
        return out

    def _trendline_break(self, candles: list[Candle], direction: int) -> bool:
        """Has price just broken the trendline he would have drawn?

        He draws it across the swing extremes of the recent leg -- descending
        across the highs when price is falling, ascending across the lows when
        rising -- and buys the break above a descending line or sells the break
        below an ascending one. A straight line through the first and last
        extreme of the window is what that amounts to.
        """
        if self.trendline_bars <= 0:
            return False
        if len(candles) < self.trendline_bars + 1:
            return False
        window = candles[-self.trendline_bars:]
        bar = candles[-1]

        if direction > 0:
            # Descending line across the highs; buying its break.
            hi = [(i, c.high) for i, c in enumerate(window)]
            first = min(hi[: len(hi) // 2], key=lambda x: -x[1])
            last = min(hi[len(hi) // 2:], key=lambda x: -x[1])
            if last[0] == first[0] or last[1] >= first[1]:
                return False        # not descending
            slope = (last[1] - first[1]) / (last[0] - first[0])
            at_now = first[1] + slope * (len(window) - 1 - first[0])
            prev = window[-2].close if len(window) > 1 else bar.open
            return prev <= at_now < bar.close

        # Ascending line across the lows; selling its break.
        lo = [(i, c.low) for i, c in enumerate(window)]
        first = min(lo[: len(lo) // 2], key=lambda x: x[1])
        last = min(lo[len(lo) // 2:], key=lambda x: x[1])
        if last[0] == first[0] or last[1] <= first[1]:
            return False            # not ascending
        slope = (last[1] - first[1]) / (last[0] - first[0])
        at_now = first[1] + slope * (len(window) - 1 - first[0])
        prev = window[-2].close if len(window) > 1 else bar.open
        return prev >= at_now > bar.close

    def _volume_ok(self, candles: list[Candle], now: datetime) -> bool:
        """The entry bar leads the session on volume, as his entry candle did."""
        if not self.volume_leads_session:
            return True
        window = self._session_window(now)
        if window is None:
            return True
        start, _end = window
        session_bars = [c for c in candles
                        if c.timestamp.astimezone(timezone.utc) >= start]
        if len(session_bars) < 2:
            return True
        bar = candles[-1]
        if bar.volume <= 0:
            return True          # no volume feed is not a reason to refuse him
        return bar.volume >= max(c.volume for c in session_bars)

    def _opposing_structure(
        self, candles: list[Candle], entry: float, long: bool
    ) -> float | None:
        """Nearest structure in the way of the target, if any."""
        window = candles[-self.zone_lookback:]
        best: float | None = None
        for i in range(4, len(window) - 4):
            bar = window[i]
            if long:
                if not all(bar.high >= window[j].high
                           for j in range(i - 4, i + 5) if j != i):
                    continue
                if bar.high <= entry:
                    continue
                if best is None or bar.high < best:
                    best = bar.high
            else:
                if not all(bar.low <= window[j].low
                           for j in range(i - 4, i + 5) if j != i):
                    continue
                if bar.low >= entry:
                    continue
                if best is None or bar.low > best:
                    best = bar.low
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
        if len(candles) < max(self.trend_bars, self.zone_lookback) + 5:
            return []

        # Position management first, above every entry gate. A gate that returns
        # early would silently disable all of this -- the mistake that made a
        # "3 hour cap" run trades for 1425 minutes earlier in this project.

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
                ahead = ((price - pos.entry_price) if pos.is_long
                         else (pos.entry_price - price))
                if ahead < risk * self.breakeven_at:
                    continue
                done = (pos.stop_loss >= pos.entry_price if pos.is_long
                        else pos.stop_loss <= pos.entry_price)
                if not done:
                    return [AdjustStop(ticket=pos.ticket,
                                       stop_loss=pos.entry_price,
                                       take_profit=pos.take_profit)]

        # "I'm gonna take half my profits here"
        if self.scale_at > 0:
            for pos in context.open_positions:
                if pos.comment != self.name or pos.stop_loss is None:
                    continue
                risk = abs(pos.entry_price - pos.stop_loss)
                if risk <= 0:
                    continue
                price = context.bid if pos.is_long else context.ask
                ahead = ((price - pos.entry_price) if pos.is_long
                         else (pos.entry_price - price))
                if ahead >= risk * self.scale_at:
                    half = round(pos.lots / 2, 2)
                    if half >= 0.01 and pos.lots > 0.01:
                        return [Exit(ticket=pos.ticket, lots=half,
                                     reason="half-off")]

        # "we're doubling up on that position... I'm pretty confident"
        # Only into a winner, and only while the original stop still protects
        # the whole thing -- he adds because it is working, not to rescue it.
        if self.add_at > 0:
            for pos in context.open_positions:
                if pos.comment != self.name or pos.stop_loss is None:
                    continue
                risk = abs(pos.entry_price - pos.stop_loss)
                if risk <= 0:
                    continue
                price = context.ask if pos.is_long else context.bid
                ahead = ((price - pos.entry_price) if pos.is_long
                         else (pos.entry_price - price))
                if ahead < risk * self.add_at:
                    continue
                # One add per original trade. Counting positions on this symbol
                # is what bounds it, so nothing has to survive a restart.
                mine = [p for p in context.open_positions if p.comment == self.name]
                if len(mine) > self.max_adds:
                    continue
                return [Enter(
                    side=pos.side,
                    stop_loss=pos.stop_loss,
                    take_profit=pos.take_profit,
                    comment=self.name,
                )]

        # -- entries ------------------------------------------------------

        if context.has_position:
            return []
        if self.skip_fridays and context.now.weekday() == 4:
            return []
        if self._trades_today(context) >= self.max_trades_per_day:
            return []
        # "First trade works out, we're done. We don't go for a second. First
        # trade doesn't work out, we look for a second one." A winner ends his
        # day exactly like two losers do.
        if context.risk.wins_today(self.name) >= 1:
            return []
        # "we are done for the day and we come back tomorrow"
        if (self.max_losses_per_day > 0
                and context.risk.losses_today(self.name) >= self.max_losses_per_day):
            return []
        if context.news is not None and context.news.active:
            return []

        # "you only trade during New York session"
        window = self._session_window(context.now)
        if window is None:
            return []
        start, end = window
        utc = context.now.astimezone(timezone.utc)
        if not (start <= utc <= end):
            return []

        # "pair that with which way is the market moving currently"
        direction = self._direction(candles)
        if direction == 0:
            return []

        # "The biggest key here, we're waiting for volume to come in"
        if not self._volume_ok(candles, context.now):
            return []

        bar = candles[-1]

        # "our entry came from this 4-hour liquidity sweep" -- price pushes past
        # an old extreme, fails, and comes back. Its own trigger.
        if self.use_liquidity_sweep:
            swept = liquidity_sweep(candles)
            if swept != 0 and swept == direction:
                window = candles[-40:]
                extreme = (min(c.low for c in window) if direction > 0
                           else max(c.high for c in window))
                pad = extreme * self.zone_pct
                stop = extreme - pad if direction > 0 else extreme + pad
                if (stop < bar.close) if direction > 0 else (stop > bar.close):
                    risk = abs(bar.close - stop)
                    target = (bar.close + risk * self.reward if direction > 0
                              else bar.close - risk * self.reward)
                    return [Enter(
                        side=OrderSide.BUY if direction > 0 else OrderSide.SELL,
                        stop_loss=stop, take_profit=target, comment=self.name)]

        # "we're getting in as soon as this trend line OR the support zone
        # breaks" -- the trendline break is a trigger on its own, so it is
        # checked before the zones rather than as an extra condition on them.
        if self._trendline_break(candles, direction):
            structure = (min(c.low for c in candles[-self.trendline_bars:])
                         if direction > 0
                         else max(c.high for c in candles[-self.trendline_bars:]))
            pad = structure * self.zone_pct
            if direction > 0:
                stop = structure - pad
                if stop < bar.close:
                    risk = bar.close - stop
                    return [Enter(side=OrderSide.BUY, stop_loss=stop,
                                  take_profit=bar.close + risk * self.reward,
                                  comment=self.name)]
            else:
                stop = structure + pad
                if stop > bar.close:
                    risk = stop - bar.close
                    return [Enter(side=OrderSide.SELL, stop_loss=stop,
                                  take_profit=bar.close - risk * self.reward,
                                  comment=self.name)]
        for z in self._zones(candles):
            # Buying needs a resistance to break. "if we're going to look for
            # buys, we need to see a resistance or a trend line break."
            if direction > 0 and z.is_resistance:
                if bar.close <= z.price:
                    continue
                # "closed not only a ginormous bullish engulfing candle but it
                # closed above the tops of those rejections"
                if self.use_engulfing and engulfing(candles, beyond=z.price) != 1:
                    continue
                stop = z.structure - (z.structure * self.zone_pct)
                # "that other fair value gap now supporting price" -- if a gap
                # sits between the entry and the stop, the stop goes behind it.
                if self.use_fair_value_gap:
                    gap = fair_value_gap(candles)
                    if gap is not None and gap[0] < bar.close and gap[0] > stop:
                        stop = gap[0] - gap[0] * self.zone_pct
                # Only sane if the structure is genuinely below the entry.
                if stop >= bar.close:
                    continue
                risk = bar.close - stop
                target = bar.close + risk * self.reward
                if self.block_into_structure > 0:
                    wall = self._opposing_structure(candles, bar.close, long=True)
                    if wall is not None and wall < bar.close + (
                        target - bar.close
                    ) * self.block_into_structure:
                        continue
                return [Enter(side=OrderSide.BUY, stop_loss=stop,
                              take_profit=target, comment=self.name)]

            # "If we were to break through this support zone here, that would
            # mean we're looking for sell positions."
            if direction < 0 and not z.is_resistance:
                if bar.close >= z.price:
                    continue
                if self.use_engulfing and engulfing(candles, beyond=z.price) != -1:
                    continue
                stop = z.structure + (z.structure * self.zone_pct)
                if self.use_fair_value_gap:
                    gap = fair_value_gap(candles)
                    if gap is not None and gap[1] > bar.close and gap[1] < stop:
                        stop = gap[1] + gap[1] * self.zone_pct
                if stop <= bar.close:
                    continue
                risk = stop - bar.close
                target = bar.close - risk * self.reward
                if self.block_into_structure > 0:
                    wall = self._opposing_structure(candles, bar.close, long=False)
                    if wall is not None and wall > bar.close - (
                        bar.close - target
                    ) * self.block_into_structure:
                        continue
                return [Enter(side=OrderSide.SELL, stop_loss=stop,
                              take_profit=target, comment=self.name)]

        return []

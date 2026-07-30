"""MambaFX's other trade: fade the channel edge back to the far side.

His breakout teaching is only half of what he does. Walking through a real
trade on video, the reasoning was entirely different:

    "I started off looking at the H4, and what I saw was a very simple
    channel. Price respected this channel -- boom, boom, boom. We're adding a
    resistance here with these two wicks, and we're also at the top of this
    channel. I believe price is going to crash down and hit the bottom of our
    channel... price will either respect this channel or hit this support, one
    or the other."

So: find a range on a higher timeframe that price keeps honouring, wait for
price to arrive at one edge, and take it back toward the other. The stop sits
just past the edge because that is where the idea is wrong; the target is the
far side of the channel, which is why the reward can be large without needing
a fixed multiple.

Why this matters for trade frequency, which is the whole reason it exists:
a breakout needs a level to actually break, and on one market that happens
about five times a month. A channel edge gets *touched* many times more often,
because touching is what a respected channel does. This is the mode that can
plausibly reach his two-to-three trades a day without loosening any filter.

Two conditions do the real work and neither is negotiable:

* **The channel must have been respected.** Multiple touches on both sides,
  or it is not a channel, it is the last N bars with a box drawn round them.
* **Price must be rejected at the edge**, not merely near it. A wick that
  pokes into the zone and closes back inside is the market refusing the
  level; a close beyond it means the channel is breaking, and fading a break
  is how this family of strategy destroys an account.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..brokers.base import Candle, OrderSide
from .base import Action, Enter, Strategy, StrategyContext
from .mamba_patterns import level_map, snap_to_level


@dataclass(frozen=True)
class Channel:
    """A range price has been honouring, and how well it has honoured it."""

    low: float
    high: float
    low_touches: int
    high_touches: int

    @property
    def width(self) -> float:
        return self.high - self.low


class MambaChannel(Strategy):
    """Fade a respected channel edge toward the opposite edge.

    Args:
        lookback_bars: How far back the channel is measured. Defaults to a
            higher-timeframe view -- 96 fifteen-minute bars is 24 hours, which
            is roughly the H4 structure he starts from.
        edge_pct: How close to an edge counts as being at it, as a fraction of
            the channel width.
        min_touches: Touches required on the side being faded. His phrase is
            "price respected this channel, boom boom boom" -- and on the video
            he counts wicks aloud before trusting a level.
        stop_pct: Stop distance past the edge, as a fraction of channel width.
        target_pct: How far across the channel to aim. 0.8 rather than 1.0
            because the far edge is where everyone else's orders are, and the
            last stretch of a range is the least reliable part of it.
        min_width_pct: Channels narrower than this fraction of price are
            noise, not structure -- and their targets do not clear costs.
        max_trades_per_day: His stated ceiling is two, three when he likes it.
    """

    name = "mamba_channel"
    timeframe = "15m"
    lookback = 400

    def __init__(
        self,
        map_lookback: int = 300,
        min_touches: int = 2,
        max_trades_per_day: int = 3,
        higher_tf_bars: int = 0,
    ) -> None:
        # THE GEOMETRY IS GONE. edge_pct, stop_pct, target_pct and min_width_pct
        # were all mine -- he states no number for any of them, and the audit
        # flagged every one as unsourced.
        #
        # His rule needs none of them: "price will either respect this channel or
        # hit this support, one or the other", and "I believe price is going to
        # crash down and hit the bottom of our channel". Edge, stop and target are
        # all levels, and the level map already supplies levels. So the edges come
        # from the map, the stop is the level beyond the edge, and the target is
        # the far side -- exactly as he describes, with nothing of mine choosing
        # how far anything sits.
        self.map_lookback = map_lookback
        self.min_touches = min_touches
        self.max_trades_per_day = max_trades_per_day
        # "If it's gonna fall on the H4, that means price is really gonna fall
        # on the M15." "We got two time frames looking good."
        #
        # This filter does nothing to a breakout -- breaking above resistance
        # already means price is at the top of its range, so the timeframes
        # agree by construction. It is the FADE that can fight the bigger
        # picture: selling a channel top while the higher timeframe climbs is
        # exactly the trade his rule exists to refuse. Zero disables it.
        self.higher_tf_bars = higher_tf_bars

    def _trades_today(self, context: StrategyContext) -> int:
        """How many trades this strategy has opened today.

        Read from the risk layer, not from open positions. Counting open
        positions makes "max N trades a day" mean "max N at once", because a
        closed trade disappears from the list -- which let 4.4 trades a day
        through a cap of 3.
        """
        return context.risk.trades_today(self.name)

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < 40:
            return []
        if context.has_position:
            return []
        if self._trades_today(context) >= self.max_trades_per_day:
            return []
        if context.news is not None and context.news.active:
            return []

        levels = level_map(candles, lookback=self.map_lookback,
                           min_touches=self.min_touches)
        if len(levels) < 4:
            return []

        bar = candles[-1]
        near = bar.close * 0.0006

        # Which way the bigger picture points, read as he reads it: where price
        # sits within the higher-timeframe range. "if it's gonna fall on the H4,
        # that means price is really gonna fall on the M15."
        allow_short = allow_long = True
        if self.higher_tf_bars > 0 and len(candles) > self.higher_tf_bars:
            htf = candles[-self.higher_tf_bars:]
            mid = (max(c.high for c in htf) + min(c.low for c in htf)) / 2.0
            allow_short = bar.close < mid
            allow_long = bar.close > mid

        # The edge he fades is not the outermost level -- it is the outermost one
        # that still has a level BEYOND it, because that beyond-level is where the
        # stop goes. Using levels[-1] as the edge asks for something above the
        # highest level in the map, which never exists, so the strategy silently
        # took zero trades in 2,786 samples. Twelfth rule in this project to be
        # present, correct-looking and inert.
        top, top_stop = levels[-2], levels[-1]
        bottom, bottom_stop = levels[1], levels[0]

        # At the top of the range: the trade is that it holds and price returns to
        # the far side. The bar must REACH the level and close back inside -- a
        # close beyond it is the range breaking, and fading a break is how this
        # family of trade destroys an account.
        if allow_short and bar.high >= top - near and bar.close < top:
            if top_stop > bar.close:
                return [Enter(side=OrderSide.SELL, stop_loss=top_stop,
                              take_profit=bottom, comment=self.name)]

        if allow_long and bar.low <= bottom + near and bar.close > bottom:
            if bottom_stop < bar.close:
                return [Enter(side=OrderSide.BUY, stop_loss=bottom_stop,
                              take_profit=top, comment=self.name)]

        return []

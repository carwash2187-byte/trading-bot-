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
        lookback_bars: int = 96,
        edge_pct: float = 0.15,
        min_touches: int = 2,
        stop_pct: float = 0.08,
        target_pct: float = 0.8,
        min_width_pct: float = 0.004,
        max_trades_per_day: int = 3,
    ) -> None:
        self.lookback_bars = lookback_bars
        self.edge_pct = edge_pct
        self.min_touches = min_touches
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.min_width_pct = min_width_pct
        self.max_trades_per_day = max_trades_per_day

    def _channel(self, candles: list[Candle]) -> Channel | None:
        window = candles[-self.lookback_bars:]
        if len(window) < 20:
            return None

        high = max(c.high for c in window)
        low = min(c.low for c in window)
        width = high - low
        if width <= 0 or width / high < self.min_width_pct:
            return None

        # A touch is a bar reaching into the outer band of the channel. This is
        # what he counts on the chart: the wicks that got there and stopped.
        band = width * self.edge_pct
        return Channel(
            low=low,
            high=high,
            low_touches=sum(1 for c in window if c.low <= low + band),
            high_touches=sum(1 for c in window if c.high >= high - band),
        )

    def _trades_today(self, context: StrategyContext) -> int:
        today = context.now.astimezone(timezone.utc).date()
        return sum(
            1 for p in context.open_positions
            if p.comment == self.name and p.opened_at.date() == today
        )

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

        channel = self._channel(candles)
        if channel is None:
            return []

        bar = candles[-1]
        band = channel.width * self.edge_pct
        stop_room = channel.width * self.stop_pct

        # At the top: the trade is that the channel holds and price returns.
        # Requires the bar to have REACHED the zone and CLOSED back inside it.
        # A close above the high is the channel breaking, and fading that is
        # the losing side of this trade.
        if (channel.high_touches >= self.min_touches
                and bar.high >= channel.high - band
                and bar.close < channel.high):
            stop = channel.high + stop_room
            risk = stop - bar.close
            if risk > 0:
                return [Enter(
                    side=OrderSide.SELL,
                    stop_loss=stop,
                    take_profit=bar.close - channel.width * self.target_pct,
                    comment=self.name,
                )]

        if (channel.low_touches >= self.min_touches
                and bar.low <= channel.low + band
                and bar.close > channel.low):
            stop = channel.low - stop_room
            risk = bar.close - stop
            if risk > 0:
                return [Enter(
                    side=OrderSide.BUY,
                    stop_loss=stop,
                    take_profit=bar.close + channel.width * self.target_pct,
                    comment=self.name,
                )]

        return []

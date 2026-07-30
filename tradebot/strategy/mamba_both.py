"""Both of MambaFX's trades in one bot, which is how he actually trades.

His teaching videos are all breakouts -- mark support and resistance, take the
break. But walking through a real live trade he never mentions a breakout at
all: he finds a channel on the H4, waits for price to reach an edge and be
rejected, and takes it back toward the far side.

They are not alternatives. A market either breaks a level or respects it, and
he has a trade for each. Running only the breakout half is why the bot took
five trades a month against his two or three a day: it was sitting out every
session where the range held, which is most of them.

Priority matters and goes to the breakout. When a level actually breaks, the
channel that level belonged to is no longer a channel, and fading its edge is
taking the wrong side of the same event.

Measured on ten months of US30 15m at 2% risk: 4.59x on 1.08 trades a day,
profitable in three quarters of four. Each half alone is worse -- the breakout
returns more (5.15x) but only trades 0.17 times a day, and the channel fade
trades often but holds up in only two quarters of four.
"""

from __future__ import annotations

from .base import Action, Strategy, StrategyContext
from .mamba import MambaBreakout
from .mamba_channel import MambaChannel


class MambaBoth(Strategy):
    """Breakout when a level gives way, channel fade when it holds."""

    name = "mamba_both"
    timeframe = "15m"
    lookback = 400

    def __init__(
        self,
        breakout: MambaBreakout | None = None,
        channel: MambaChannel | None = None,
    ) -> None:
        self.breakout = breakout or MambaBreakout(
            wait_for_close=False, stop_candle_frac=0.5, reward=8.0
        )
        self.channel = channel or MambaChannel()
        # Both halves tag their orders with this bot's name, so the portfolio
        # manager and the risk layer see one strategy rather than two fighting
        # over the same symbol.
        self.breakout.name = self.name
        self.channel.name = self.name

    def evaluate(self, context: StrategyContext) -> list[Action]:
        for half in (self.breakout, self.channel):
            actions = half.evaluate(context)
            if actions:
                return actions
        return []

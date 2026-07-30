"""Everything MambaFX does, in one strategy, so it trades every day like he does.

He does not run one setup on one market. His watchlist is visible on screen --
gold, LTC, FIL, BTC, ETH, XRP, NAS100, US30 -- and he says outright which of
those he lives on:

    "i'm actually going to be full time trading just nasdaq us 30 gbp usd and all
    of my cryptos and that's going to be it for now"

And he trades all of them, every day:

    "With New York session, 6:30 every morning is always the time to trade"
    "Tomorrow, I'll do it again. I'll make more"
    "New York session's okay, but Tokyo session for me is better for gold"

That is why a single setup on a single market cannot reproduce him. Measured on
US30 alone, the best build here trades 0.52 times a day and does nothing at all
on 71 days out of 220. He is never flat for 71 days. The trades are spread across
markets and across setups, and any one of them being quiet is covered by the
others being busy.

This class runs each of his setups in turn on whatever market it is pointed at.
Combined with running it on his whole watchlist at once, that is the shape of his
actual day: several markets open, several setups armed, two or three fire.

Order matters and follows how decisive the signal is:

1. **The New York session break.** His bread and butter, and time-limited -- if
   the 6:30 window is live and a level goes, that is the trade he takes.
2. **Break and retest.** His small-account method, and the entry he says is
   easiest to catch because you can wait for it.
3. **Channel fade.** What he does when a level holds instead of breaking.

A market either breaks a level or respects it, so at most one of these has a real
signal at a time. The order only decides what happens in the rare tie, and it
gives the tie to the more time-sensitive trade.
"""

from __future__ import annotations

from .base import Action, Strategy, StrategyContext
from .mamba_channel import MambaChannel
from .mamba_ny import MambaNY
from .mamba_retest import MambaRetest


class MambaAll(Strategy):
    """All of his setups on one market, so a whole watchlist can be covered."""

    name = "mamba_all"
    timeframe = "15m"
    lookback = 500

    def __init__(
        self,
        ny: MambaNY | None = None,
        retest: MambaRetest | None = None,
        channel: MambaChannel | None = None,
        timeframe: str = "15m",
    ) -> None:
        # MambaNY is written for his 5-minute chart. Pointed at 15-minute bars it
        # still works, but its bar-count windows mean three times as much clock
        # time, so they are scaled when the timeframe is coarser.
        scale = 1 if timeframe == "5m" else 3
        self.ny = ny or MambaNY(
            zone_lookback=72 // scale or 24,
            trend_bars=48 // scale or 16,
            max_hold_minutes=35 * scale,
        )
        self.retest = retest or MambaRetest(ma_period=50, trail_after=6.0)
        self.channel = channel or MambaChannel(higher_tf_bars=32)

        # All three tag their orders with this bot's name, so the risk layer and
        # the portfolio manager see one strategy rather than three fighting over
        # the same symbol -- and so the per-day trade and loss counters cover the
        # bot as a whole, which is how he counts his own day.
        for half in (self.ny, self.retest, self.channel):
            half.name = self.name

        self.timeframe = timeframe

    def evaluate(self, context: StrategyContext) -> list[Action]:
        for half in (self.ny, self.retest, self.channel):
            actions = half.evaluate(context)
            if actions:
                return actions
        return []

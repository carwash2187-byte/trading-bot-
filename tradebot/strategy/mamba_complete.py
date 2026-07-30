"""Every strategy MambaFX has, in one bot, with nothing of mine overriding him.

The other files each hold one of his setups. This holds all of them, and it puts
back the two rules I had switched off because they tested worse — which was me
overruling ten years of his live screens with ten months of replayed history.

**His direction rule is back on and comes first**, because that is the order he
states it in:

    "how i'm trading it is first off i need to determine are we going up are we
    going down are we in a bullish trend or a bearish trend are you making bullish
    moves or bearish moves right and that's going to be from the daily and the
    four hour"

    "we're gonna start on the h4 always h4 you can use the daily as well i like
    the h4"

**Every setup he teaches is armed**, tried in the order of how decisively he
describes taking it:

1. **New York session break** — his bread and butter, and time-limited, so it goes
   first. "there's only two things we're looking for. We're looking for a break of
   a support or a break of resistance, but we also want to pair that with which
   way is the market moving currently."
2. **Fibonacci gold zone** — his most-mentioned tool. "the fibonacci is just a
   zero point five or six one eight zone that's the only zones I want to see get
   rejected."
3. **Break and retest** — his small-account method. "price broke below these lows
   came back and as you can see retested it."
4. **The three-confirmation setup** — RSI at 75/25 with Bollinger 34. "this is
   where it's important the upper band needs to be 75 and the lower band needs to
   be 25."
5. **Channel fade** — what he does when a level holds instead of breaking. "price
   respected this channel -- boom, boom, boom."
6. **Pattern confluence** — the double top, engulfing candle, fair value gap,
   liquidity sweep and MACD divergence, which is what he reads when none of the
   above has a clean signal.

A market can only be doing one of these at a time — either a level breaks or it
holds, either price is retracing into a zone or it is not — so the order decides
what happens in a tie, and the tie goes to the trade he talks about taking most.

Nothing here is tuned to make the number better. Where he gives a value it is his
value. Where he gives none, the value comes from what he draws on screen.
"""

from __future__ import annotations

from .base import Action, Strategy, StrategyContext
from .mamba_channel import MambaChannel
from .mamba_fib import MambaFib
from .mamba_ny import MambaNY
from .mamba_retest import MambaRetest
from .mamba_rsi import MambaRsi
from .mamba_signals import MambaSignals


class MambaComplete(Strategy):
    """All of his setups, his direction rule, his risk discipline."""

    name = "mamba_complete"
    timeframe = "15m"
    lookback = 500

    def __init__(self, timeframe: str = "15m") -> None:
        # On 15-minute bars his 5-minute windows cover three times the clock, so
        # bar counts are scaled. Everything else is his stated number.
        scale = 1 if timeframe == "5m" else 3

        # 1. The New York break, with his trendline and his volume rule both on.
        #    "I drew up my resistance, I drew up my support, and I drew my trend
        #    line... we're getting in as soon as this trend line or the support
        #    zone breaks." / "The biggest key here, we're waiting for volume to
        #    come in."
        self.ny = MambaNY(
            zone_lookback=max(24, 72 // scale),
            trend_bars=max(16, 48 // scale),
            max_hold_minutes=35 * scale,
            trendline_bars=max(8, 24 // scale),
            volume_leads_session=True,
            breakeven_at=2.0,          # "we got to a 1 to two stops can go to break even"
            scale_at=2.0,              # "I'm gonna take half my profits here"
            add_at=1.0,                # "we're doubling up on that position"
            block_into_structure=0.8,  # "we're at a pretty strong resistance... not the smartest trade"
            use_engulfing=True,
            use_liquidity_sweep=True,
            use_fair_value_gap=True,
        )

        # 2. The gold zone, with the double top he pairs it with.
        #    "you see a double top like why is this your entry... take my
        #    Fibonacci... look at this beautiful 50 and a 6-1-8 rejection."
        self.fib = MambaFib(require_double=True)

        # 3. Break and retest, with his 50 moving average and his trail.
        self.retest = MambaRetest(ma_period=50, trail_after=6.0,
                                  breakeven_at=2.0, scale_at=2.0)

        # 4. The three-confirmation setup at the settings he reads out loud.
        self.rsi = MambaRsi()

        # 5. The channel fade, with the two-timeframe rule he applies to it.
        self.channel = MambaChannel(higher_tf_bars=32 // scale or 32)

        # 6. Pattern confluence, WITH his direction rule doing the gating --
        #    "first off i need to determine are we going up are we going down...
        #    from the daily and the four hour". H4 leads, daily can veto.
        self.signals = MambaSignals(
            min_votes=2,
            h4_bars=16 * scale // 3 or 16,
            daily_bars=96 * scale // 3 or 96,
            higher_tf_gates=True,
            breakeven_at=2.0,
            breakeven_pad=0.1,         # "stops to break even, NEAR break even"
            scale_at=2.0,
            exit_on_reason_gone=True,  # "I wasn't sure if price was going to fully reverse"
            max_hold_minutes=35 * scale,
        )

        # One name across all of them, so the risk layer counts his day as one
        # day: three trades, two losses and he is finished.
        self.halves = (self.ny, self.fib, self.retest, self.rsi,
                       self.channel, self.signals)
        for half in self.halves:
            half.name = self.name

        self.timeframe = timeframe

    def evaluate(self, context: StrategyContext) -> list[Action]:
        for half in self.halves:
            actions = half.evaluate(context)
            if actions:
                return actions
        return []

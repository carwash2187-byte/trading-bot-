"""MambaFX's signal-room trade — the most completely specified thing he does.

Every other video describes a method. This one shows the finished output: the exact
signals he posts to his own room, twice over, with identical geometry. Read off the
screen rather than inferred from anything he says.

    Entry   34540.0        Entry   34375.0
    TP1     34515.0  (1R)  TP1     34400.0  (1R)
    TP2     34490.0  (2R)  TP2     34425.0  (2R)
    TP3     34465.0  (3R)  TP3     34450.0  (3R)
    TP4     34440.0  (4R)  TP4     34475.0  (4R)
    TP5     34390.0  (6R)  TP5     34525.0  (6R)
    SL      34565.0  (1R)  SL      34350.0  (1R)

A **flat 25.0-point stop** and a **1 / 2 / 3 / 4 / 6 R ladder**, identical on the sell
and the buy, unchanged by entry price or direction. His own hit messages confirm the
arithmetic — "TP 1 HIT +250 pips" through "TP 5 HIT +1500 pips 1:6RR that's a wrap",
so his "pip" on an index is a tenth of a point.

The footer on every signal states the risk:

    "Please do not over risk! 1-3% max risk per trade!"

The rest, from the same video:

* **US30 only.** "let's just look at us 30 for an example... I'm killing us 30."
* **Around six in the morning.** "you should be trading at around six o'clock in the
  morning because that's when things are moving, that's when you get the most volume."
  His chart clock reads UTC-8, so that is 06:00 Pacific — 14:00 UTC. His room's own
  stamps run 6:17-6:46 for entries and wrap up by 7:27-7:47, a window of about 105
  minutes.
* **One trade a day.** The room's date separators each carry a single entry with its
  take-profit replies beneath.
* **5-minute for direction, 1-minute for the entry.** "on the five minute chart here we
  can see price is trending to the downside" then "I'm going to go down to the one
  minute... because five minutes kind of a little choppy, I'm not seeing enough clarity."
* **Intrabar, and waiting for the close is his own stated mistake.** "price starts to
  break below, take my short position on this candle close — which usually I would
  actually get in before the candle closes. Kind of a late entry, I should have entered
  up here."
* **He has ABANDONED break-and-retest.** "the problem with this is I'm waiting for that
  retest, and when you wait for that retest and it doesn't come you're missing out on
  pips, you're missing out on trades... it just takes too long." That is the method
  `mamba_retest.py` implements, and he describes it in the past tense as the thing he
  stopped doing.
* **And he refuses 1:1.** "I wasn't going for anything higher than a risk of one to one
  ... I was tired of hitting one to ones and maybe a one to two at best."

On whether this is even executable: his broker prices US30 at $100 per point per lot, so
his own minimum 0.01 lot on a 25-point stop risks $25 — 16.7% of a $150 account, far
outside the 1-3% his own signals demand. Leo's broker prices US30 at **$1 per point per
lot**, a hundred times smaller, so 0.01 lot on the same 25-point stop risks **$0.25, or
0.17%**. His exact trade fits Leo's account and does not fit his own.
"""

from __future__ import annotations

from datetime import timedelta, timezone

from ..brokers.base import Candle, OrderSide
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext


class MambaRoom(Strategy):
    """His posted signal: 5m direction, 1m break, flat stop, 1/2/3/4/6R ladder.

    Args:
        stop_points: 25.0 — the flat stop on every signal he posts, unchanged by
            entry price or direction.
        ladder: (1, 2, 3, 4, 6) — his take-profit rungs in R.
        open_hour_utc / window_minutes: 14:00 UTC for "around six o'clock in the
            morning" on his UTC-8 clock, and 105 minutes to cover his room's
            6:17-7:47 spread of entries and wrap-ups.
        trend_bars: bars used for the 5-minute direction read.
        break_bars: bars whose extreme the 1-minute break must clear.
        max_trades_per_day: 1 — his room posts one signal a day.
    """

    name = "mamba_room"
    timeframe = "1m"
    lookback = 600

    def __init__(
        self,
        stop_points: float = 25.0,
        ladder: tuple[float, ...] = (1.0, 2.0, 3.0, 4.0, 6.0),
        open_hour_utc: int = 14,
        window_minutes: int = 105,
        trend_bars: int = 75,
        break_bars: int = 20,
        max_trades_per_day: int = 1,
        max_losses_per_day: int = 2,
    ) -> None:
        self.stop_points = stop_points
        self.ladder = ladder
        self.open_hour_utc = open_hour_utc
        self.window_minutes = window_minutes
        self.trend_bars = trend_bars
        self.break_bars = break_bars
        self.max_trades_per_day = max_trades_per_day
        self.max_losses_per_day = max_losses_per_day

    def _in_window(self, now) -> bool:
        utc = now.astimezone(timezone.utc)
        start = utc.replace(hour=self.open_hour_utc, minute=0,
                           second=0, microsecond=0)
        return start <= utc <= start + timedelta(minutes=self.window_minutes)

    def _direction(self, candles: list[Candle]) -> int:
        """The 5-minute read, taken from five times as many 1-minute bars.

        "on the five minute chart here we can see price is trending to the
        downside... we have a bearish market, when I see a bearish market I'm
        looking for sales."
        """
        if len(candles) < self.trend_bars:
            return 0
        window = candles[-self.trend_bars:]
        first = window[: len(window) // 2]
        last = window[len(window) // 2:]
        a = sum(c.close for c in first) / len(first)
        b = sum(c.close for c in last) / len(last)
        if b > a:
            return 1
        if b < a:
            return -1
        return 0

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < self.trend_bars + self.break_bars + 5:
            return []

        # The ladder, run off the stop distance the trade opened with. Each rung
        # takes a slice and the stop follows -- "TP 1 HIT... TP 2 HIT... 1:6RR
        # that's a wrap".
        for pos in context.open_positions:
            if pos.comment != self.name or pos.stop_loss is None:
                continue
            risk = abs(pos.entry_price - pos.stop_loss)
            if risk <= 0:
                continue
            price = context.bid if pos.is_long else context.ask
            ahead = ((price - pos.entry_price) if pos.is_long
                     else (pos.entry_price - price))
            banked = (pos.stop_loss >= pos.entry_price if pos.is_long
                      else pos.stop_loss <= pos.entry_price)
            # First rung: take a slice and lift the stop to entry.
            if ahead >= risk * self.ladder[0] and not banked:
                slice_lots = round(pos.lots / len(self.ladder), 2)
                if slice_lots >= 0.01 and pos.lots > 0.01:
                    return [Exit(ticket=pos.ticket, lots=slice_lots,
                                 reason="tp1")]
                return [AdjustStop(ticket=pos.ticket, stop_loss=pos.entry_price,
                                   take_profit=pos.take_profit)]
            # Later rungs: walk the stop up behind price, one rung at a time.
            for rung in self.ladder[1:]:
                if ahead < risk * rung:
                    break
                want = (pos.entry_price + risk * (rung - 1) if pos.is_long
                        else pos.entry_price - risk * (rung - 1))
                better = (want > pos.stop_loss if pos.is_long
                          else want < pos.stop_loss)
                if better:
                    return [AdjustStop(ticket=pos.ticket, stop_loss=want,
                                       take_profit=pos.take_profit)]

        if context.has_position:
            return []
        if context.risk.trades_today(self.name) >= self.max_trades_per_day:
            return []
        if (self.max_losses_per_day > 0
                and context.risk.losses_today(self.name) >= self.max_losses_per_day):
            return []
        if context.news is not None and context.news.active:
            return []
        if not self._in_window(context.now):
            return []

        direction = self._direction(candles)
        if direction == 0:
            return []

        bar = candles[-1]
        window = candles[-self.break_bars:-1]
        if not window:
            return []

        # "look for support to be broken, look for a trend line to be broken" --
        # and intrabar, because waiting for the close is his stated mistake. The
        # bar only has to REACH through the level, not close beyond it.
        if direction < 0:
            level = min(c.low for c in window)
            if bar.low > level:
                return []
            stop = bar.close + self.stop_points
            target = bar.close - self.stop_points * self.ladder[-1]
            return [Enter(side=OrderSide.SELL, stop_loss=stop,
                          take_profit=target, comment=self.name)]

        level = max(c.high for c in window)
        if bar.high < level:
            return []
        stop = bar.close - self.stop_points
        target = bar.close + self.stop_points * self.ladder[-1]
        return [Enter(side=OrderSide.BUY, stop_loss=stop,
                      take_profit=target, comment=self.name)]

# tradebot — paper-trading infrastructure

Broker-agnostic trading plumbing. **No strategy logic is included** — no entry
rules, no exit rules, no indicator thresholds, no opinion about news. You plug
your own logic into one interface and everything else (sizing, circuit
breakers, journalling, reliability) applies to it automatically.

**111 tests, no network calls, no credentials required to run them.**

```bash
python3 -m pytest tests/ -q      # 111 passed
./run.py --symbols XAUUSD        # one paper cycle
```

---

## What's here

```
tradebot/
  instruments.py        contract specs + ALL lot/unit maths (one place, on purpose)
  brokers/
    base.py             Broker interface, bracket orders, live-mode gate
    paper.py            local simulator — no network
    tradelocker.py      REST adapter (what most prop firms run)
    mt5.py              MetaTrader5 terminal adapter
  data/
    ohlc.py             multi-year, multi-timeframe candle store + resampling
    indicators.py       RSI, ATR, SMA/EMA, VWAP, Bollinger, volume profile
  news/
    calendar.py         economic calendar + fast high-impact detection
  risk/
    sizing.py           equity- and stop-driven position sizing
    limits.py           daily-loss, max-drawdown, correlation breakers
    journal.py          persistent journal + broker reconciliation
  runtime/
    cycle.py            one guarded pass; every stage isolated
    state.py            atomic writes, self-healing on corruption
    lock.py             single-instance lock (OS-level, not a pid file)
    hours.py            real market hours per instrument
    watchdog.py         heartbeat + stale-job restart
  strategy/
    base.py             the interface you implement — deliberately empty
run.py                  scheduled-job entry point
```

---

## The five things most likely to cost real money

### 1. Lot vs unit maths

Brokers report **lots**; P&L happens in **units**. Getting this wrong misstates
every trade, sometimes by 100,000x, and nothing downstream notices. All of it
lives in `instruments.py` and nowhere else.

```python
gold = get_instrument("XAUUSD")
gold.units(1.0)                                   # 100 (ounces, NOT 100,000)
gold.pnl_in_quote(2000, 2001, lots=1.0, is_long=True)   # $100.00
```

The TradeLocker and MT5 adapters read `contract_size` **from the broker** rather
than from a local constant, so a stale spec can't silently corrupt the numbers.

### 2. Live mode can't turn on by accident

Two independent things must both be true:

```bash
export TRADEBOT_ALLOW_LIVE=yes      # in the launching shell, not a config file
./run.py --mode live ...
```

A config typo, a bad default, or a restart all land in paper. The MT5 adapter
adds a third check: it refuses to connect if the terminal is on a real account
while the bot is in demo mode.

### 3. Brackets are server-side

`submit_bracket()` sends the stop and target **attached to the entry**. The
broker holds them. Kill the process mid-trade and the position stays protected.
`BracketOrder` won't even construct without a stop-loss.

### 4. Two copies can't run at once

`InstanceLock` uses an OS advisory lock (`flock`), not a "does the pid file
exist" check. A hard kill releases it automatically, so there's no stale file to
clear — but a second copy is refused while the first is alive.

### 5. The journal is checked against the broker

Every N cycles, journal totals are compared to the broker's own balance. A
persistent mismatch is how a multiplier bug announces itself instead of quietly
lying to you.

```
[MISMATCH] journal=20000.00 broker=10100.00 diff=+9900.00 (tolerance 0.01)
```

---

## Plugging in a strategy

Subclass `Strategy`, return actions. You never place orders or pick a lot size
directly — that's what keeps risk and journalling in the loop.

```python
from tradebot.strategy.base import Strategy, Enter
from tradebot.brokers.base import OrderSide
from tradebot.data.indicators import atr

class MyStrategy(Strategy):
    timeframe = "4h"
    lookback = 300

    def evaluate(self, ctx):
        if ctx.has_position or len(ctx.candles) < 250:
            return []
        a = atr(ctx.candles, 14)[-1]
        if a is None:
            return []
        # your entry condition here
        if <your rule>:
            return [Enter(side=OrderSide.BUY, stop_loss=ctx.mid - 2 * a)]
        return []
```

Then swap it into `run.py` in place of `NoOpStrategy()`.

`ctx` gives you candles, bid/ask, account, open positions, the news window, and
the risk manager. `Enter` takes a **direction and a stop price** — size is
computed for you from equity, risk-per-trade, and the contract multiplier.

---

## Studying history

```python
from tradebot.data.ohlc import CandleStore, resample, to_ascii_chart
from tradebot.data.indicators import rsi, atr, bollinger, volume_profile

store = CandleStore("data/candles")
store.download_all_timeframes(broker, "XAUUSD",
                              ["1m", "5m", "15m", "1h", "1d"], years=3)

print(store.coverage_report("XAUUSD"))
candles = store.load("XAUUSD", "1h")
print(to_ascii_chart(candles[-200:]))          # eyeball it in the terminal

rsi(candles, 14)                                # aligned to input length
volume_profile(candles).point_of_control
resample(store.load("XAUUSD", "1h"), "1h", "4h")
```

Every indicator returns a list the **same length as the input**, front-padded
with `None`. Index `i` always means bar `i` — no off-by-one alignment bugs.

---

## News

```python
detector = NewsDetector(calendar, pre_window=300, post_window=300,
                        min_impact=Impact.HIGH)

window = detector.check("XAUUSD")        # every cycle — it's microseconds
window.is_imminent                       # release is coming
window.is_fresh                          # release just landed

detector.just_fired("XAUUSD", within_seconds=5)   # the fast reaction path
```

Benchmarked at 1,000 checks against a 50,000-event calendar in under a second,
so it runs every cycle rather than once a day. **It decides nothing** — whether
to trade into news or sit it out is your call; this is only the plumbing.

---

## Running unattended

```cron
*/5 * * * *  cd /path/to/tradebot && ./run.py --symbols XAUUSD >> logs/bot.log 2>&1
*/20 * * * * cd /path/to/tradebot && ./watchdog.py
```

- One pass per invocation, then exit — nothing long-lived to wedge.
- Every stage individually wrapped: a dropped connection or a bad tick logs and
  retries next cycle instead of killing the run.
- Corrupt state files are backed up and replaced, never fatal.
- Outside market hours the bot does nothing, quietly — no error spam all weekend.
- Run the watchdog from a *different* mechanism than the bot. A watchdog started
  by the same cron that died isn't a watchdog.

---

## Configuring for a prop firm

Match the breakers to the firm's rules, then leave headroom:

```python
RiskLimits(
    risk_per_trade=0.005,        # 0.5% per trade
    daily_loss_limit=0.02,       # halt at -2% when the firm's cap is 3%
    max_drawdown_limit=0.04,     # halt at -4% when the firm's cap is 6%
    max_correlated_positions=1,
)
```

Set your halt **below** the firm's limit. Tripping your own breaker pauses
trading; tripping theirs ends the account.

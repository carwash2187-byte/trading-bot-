# What actually works

Measured on 2026-07-28 with the local backtester (`tradebot/backtest/`), which
runs the real bot code against real prices. Every number here is after costs.

## The answer: gold, not crypto

`RsiScalper` on gold (PAXG 15m), 1% risk on $10,000:

| | |
|---|---|
| profit | **+$218/month** |
| profit factor | 1.87 |
| win rate | 58% |
| max drawdown | **5.0%** — under AquaFunded's 6% cap |
| trades | 81 over 14 months |

Settings: RSI 14, oversold 30 / overbought 70, stop 1 ATR, target 1.5x the
stop, 200-bar EMA trend filter. The trend filter is not optional — without it
the same strategy loses $292/month.

## Why this one is believed and the others were not

Three tests, all of which the crypto strategies failed:

**Walk-forward: 4 of 4 stretches profitable**, including the most recent. The
crypto walk-forward was a coin flip — nearly every coin won 3 of 5 stretches,
and the two that won 4 of 5 both lost money in the latest one.

**All 6 parameter settings profitable.** On crypto, changing one setting swung
a coin from +$1,010/month to −$329. Winning across a range rather than at one
exact point is the difference between an effect and a fluke.

**Not a bull-run artifact.** This is what killed the earlier gold bot on this
project, so it was checked directly: shorts made *more* than longs (+$1,819 vs
+$1,394) and won more often (66% vs 54%), and the bot earned +$2,347 across the
three falling-gold stretches against +$631 across the five rising ones. It does
its best work when gold falls.

## Why gold and not crypto

Cost per round trip is roughly tenfold apart, and this strategy trades often
enough for that to decide the outcome:

| | cost per round trip |
|---|---|
| BTCUSD | 0.104% |
| gold | ~0.010% |

An earlier measurement on this project found a fast strategy earning $0.04 per
trade while paying $0.98 in fees. The edge per trade never changed; only the
toll did.

## What does not work

* **More risk stops paying.** On $10k the Big-Runner peaks at 3% risk ($94/month)
  then falls: $46 at 5%, **−$111 at 8%** with a 76% drawdown. Losses compound
  against recovery faster than wins compound for it.
* **Trading many coins at once loses money.** All 8 together: −$254/month, 80%
  drawdown. Crypto is one trade wearing eight tickers, so the losers cannot be
  diversified away — and with only 2 correlated positions allowed, they crowd
  out the winners.
* **Bitcoin is one of the worse coins**, not the best. It was also the only one
  tested for most of this project.
* **Mean reversion, pullback buying and range fading all lose on BTC 2h**
  (−$219, −$186, −$374 per month).

## Caveats that belong next to the gold number

81 trades over 14 months is a small sample. PAXG history does not start before
May 2025, so there is no way to test further back. One of the four walk-forward
stretches contains only 3 trades. And a backtest is a claim about the past —
every trader.dev figure re-checked against this engine came down sharply.

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

## How much, how often, and how likely (25 starting points)

Measured by running a fresh $10,000 account from 25 different start dates,
three months each. Twenty-five overlapping windows is a much better basis than
the four non-overlapping stretches used earlier — a "1 in 4" claim from four
samples is a coin flipped four times.

| | |
|---|---|
| typical month | **$633** |
| typical week | $146 |
| best month seen | $1,157 |
| worst month seen | −$43 |
| made money | 24/25 (**96%**) |
| cleared $500/month | 17/25 (**68%**) |
| cleared $500/week | 0/25 (**0%**) |
| account died | 4/25 (**16%**) |
| when it died | after ~20 days |

**The danger is all at the start.** Every account that died, died early — before
it had banked a cushion. Survive the first month in profit and the 6% cap stops
being a realistic threat, which is also why the single long continuous run
showed no breach at all: by the time it hit its worst fall, it was far enough
ahead that 6% below the *starting* balance was never in reach.

This corrects an earlier figure of $730–1,100/month, which came from one long
compounding run and was flattered by it.

## Reaching $500/week

Bet size decides whether the account dies. Account size decides how much it
makes. They are separate dials, and turning the first one up is how this
project kept killing accounts:

| setup | $/week | died |
|---|---|---|
| $25,000 at 1.00% | $281 | 1/4 |
| $50,000 at 1.00% | $565 | 1/4 |
| $50,000 at 0.75% | $418 | 0/4 |
| **$100,000 at 0.50%** | **$548** | **0/4** |

$25k at 1% makes $281/week and dies one time in four. $100k at 0.5% makes
$548/week and never died. Twice the money and less danger, because the bet is
half as aggressive spread over four times the capital.

**$500/month wants a $10k account. $500/week wants $100k.** No position size on
a $10k account reaches $500/week — that was checked, and past 3% risk the
profit falls while the drawdown keeps climbing.

## How far to trust these numbers

All 25 windows come from the same 14 months of gold and overlap heavily, so
they are closer to five independent tests than twenty-five. PAXG is a
gold-backed token on a crypto exchange, not the instrument that would actually
be traded, and it trades weekends when gold does not. The costs are estimated
from a screenshot rather than measured fills.

The direction of these results is trustworthy. The decimal places are not.

## Betting bigger does not unlock payouts faster

Tested across 17 starting points, $10k gold, five risk levels:

| risk | unlock | died | got paid | $/month |
|---|---|---|---|---|
| 1.5% | 32 days | 2/17 | **16/17** | $623 |
| 2% | 31 days | 4/17 | 14/17 | $844 |
| **3%** | 31 days | 6/17 | 12/17 | **$1,322** |
| 4% | 31 days | 9/17 | 10/17 | $1,824 |
| 5% | 31 days | 9/17 | 9/17 | $2,357 |

**The unlock time does not move.** It is 31 days at every level, and the reason
is that the bar was never the constraint: at 1.5% risk a winning trade already
gains 2.25%, which clears the +0.5% requirement four times over. Betting more
makes the same qualifying days larger, it does not create new ones.

What risk actually buys is money, paid for in deaths. 1.5% earns $623/month and
gets paid 16 times in 17; 3% earns $1,322 and gets paid 12 times in 17. Past 3%
the money keeps rising while "got paid" falls below two thirds — the account is
being lost before payday more often than not, and an unpaid gain is not income.

**To unlock faster the lever is trade frequency, not bet size.** Qualifying days
are days that closed up; only a third of days currently have any trade at all.
More trading days is the only thing that can raise the count, which is what
`find_fast_payout.py` searches for.

## Closed profit vs floating profit

Prop firms count balance (closed trades), not equity (which includes open
positions). Checked, because it would invalidate every payout figure above:

| basis | qualifying days | unlock |
|---|---|---|
| equity (open trades count) | 93 | day 43 |
| **balance (closed only)** | **90** | **day 43** |

Effectively identical, because every trade carries a take-profit and stop-loss
set before entry, so positions close at the broker rather than sitting open
across day boundaries. On a strategy that held positions for days this would
have mattered and end-of-day banking would be needed.

Of the 150 days where a trade closed, 90 closed up 0.5% or more — 60%. The
constraint is not the size of a winning day, it is how many days have a trade.

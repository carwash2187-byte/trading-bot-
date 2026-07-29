# MambaFx — how he trades, video by video

Mission: watch all videos, extract the method, build bot 2.

## THE METHOD SO FAR (rewritten as it firms up)

*(filling in as videos are watched)*

## Video notes

### Video: "The 3 Minute Trading Setup That Made Me RICH" (frames + full audio)

**His rules, his words:**
1. **On 3 min before New York open** ("I get on at 6:27, session starts 6:30")
2. **Only the last few hours matter.** Ignore London, ignore yesterday.
3. **Draw ONE resistance and ONE support** (recent swing zones). Two zones max.
   "Doing too much is the number one killer."
4. **Trade the break:** above resistance -> BUY, below support -> SELL.
   "Drew resistance, drew support, wait for a break. The rest is history."
5. **Target 1:5.** "Lose two trades, one works, still make a s***ton."
6. **Failed break -> take the next one, including the reverse:** "Comes back
   down, I take a loss. Pushes down, I take a sell. Hits 1:5, up 1:4 on the day."
7. **Fixed small risk %** (worked example 5%: "you can lose 20 trades").
8. **One session, then done.** "Win and a loss is the same thing. Go golfing."

**Codeable shape:** NY-open breakout. Pre-open range = S/R; first break = entry
with 1:5 bracket; one re-entry allowed on the reverse break; flat after session.

**To pin down:** exact stop placement, wick-vs-close breakout confirmation,
which market (indices futures at NY open vs forex pairs).

**SEEN WITH EYES (frame 82, TradingView replay):**
- Market: **US30 / Dow Jones index**, small-timeframe candles (1-5m)
- S/R drawn as **zone BANDS** (rectangles a few points thick) across the swing
  highs/lows of the last few hours — not single lines
- Long-position tool on the resistance break: **stop = thin red band tucked
  just UNDER the broken zone**; target = tall green box ~5x the stop distance
- So: tight stop under the zone is what makes 1:5 reachable

### Video: "Breakout Trading Made SIMPLE in 10 Minutes" (frames + full captions)

**This video overrides my earlier guesses. Corrections in bold.**

* **Markets: Nasdaq (NQ) and US30 (YM) ONLY.** "I'm not going to look at gold.
  I'm not going to look at XRP... I'm only trading Nasdaq and US30 every day."
* **Timeframes: 5 and 15 minute, sometimes 1.** "We're never going to the 30.
  We're not on the hourly. Always the 15, the 5, or the 1." Choppy -> 15,
  clean volume -> 5, and he drops to 1m only to time the entry on a break.
* **ONE session, not three.** "6:20 a.m. Pacific" to mark up, "6:30 volume
  kicks in" -- that is 13:30/14:30 UTC, the New York open. The "three
  sessions" in the course video is his paid room's coverage, not his own
  trading.
* **A zone is only valid at 3-4+ touches.** "Three or four touches, that's
  enough for me." Nine touches = "a f***ing resistance."
* **Trendline breaks count too**, and a trendline break that is ALSO an S/R
  break is his favourite ("you have both breaks").
* **Target 1:3 minimum, 1:5 max.** Not a flat 1:5 -- "a simple one to three
  max, one to three minimum I should say, one to five max."
* **Fakeouts are not predicted, they are absorbed.** "You don't detect
  fakeouts... if it fakes out and you lose, it comes back, breaks again, we
  re-enter." Take the second break, and the third.
* **Two trades a day, three if he is feeling it.** Hard ceiling.
* Stop goes just past the broken level; he shows one placed under the
  breakout candle's zone.

**Net effect on the bot:** wrong on sessions (NY only), wrong on the fixed 1:5
(range 3-5), and missing the touch-count filter entirely -- which is the rule
that decides whether a level is even tradable. All three go in next.

### "The QUICKEST Strategy To Flip Any Small Account" — his small-account method

Different from the standard breakout in two decisive ways, and this is the one
built for accounts the size of Leo's:

* **NO candle-close wait.** "We're not waiting for candle closure... as soon
  as that resistance breaks, we are entering, because we're going to
  prioritize having a very tight stop-loss and going for massive
  risk-to-rewards." Entry is the instant price crosses the zone.
* **Stop is a quarter of the breakout candle**, not a zone buffer: "very tight
  stop loss, we'll just do about a quarter of what the candle's worth."
* **Target 1:8**, stated twice: "we want to average a 1 to 8." His worked
  example is a 13-point stop against a 105-point target.
* He accepts the consequence explicitly: "you're going to get stopped out more
  than usual... you may lose two times, three times, but eventually you're
  going to find that breakout."
* Small-account maths he shows: $50 account risking $5. Lose three, win one at
  1:8 and the account is $75 -- up 50%.

### "The Only 1-Minute Scalping Strategy" — the timeframe structure

* "We ALWAYS start on our 5-minute, we look for support or resistance, we try
  to find which direction the market is moving, THEN we go down to our
  1-minute to find entry."
* So the 1-minute is the entry trigger, not the analysis chart. Zones come
  from the 5m; the 1m only times the fill.
* In a challenge video he trades US30, NASDAQ, Gold and S&P -- so the "only
  Nasdaq and US30" line is his daily habit, not a hard restriction.

## THE BUILD THAT WORKS (bot 2, registered as `mamba`)

US30, 15-minute bars, New York session:

| | |
|---|---|
| entry | the instant price crosses the zone -- no candle-close wait |
| stop | half the breakout candle |
| target | 1:8 |
| zones | 3-hour pre-session range, 3+ touches required |
| trades | 2 per session |

**Ten months, $2,635 at 1.5% risk: +$2,240, ending $4,875. 51 trades, 25.5%
win rate, profit factor 1.99, worst drop 18%.** Profitable in all four unseen
stretches -- the only one of ~90 configurations tested that was.

Risk ladder on a live account: 1.5% -> $219/mo (18% drop), 3% -> $541/mo
(28%), 5% -> $1,030/mo (34%). Unlike gold, the money keeps climbing with risk
instead of collapsing, because a 1:8 payout survives being sized up.

**Timeframe is decisive and counterintuitive.** The same rules on 1-minute
bars lose $3,000-6,000 a month: zones become noise, breaks become noise, and a
half-candle stop is often under one tick. He says "the 15, the 5, or the 1" --
the 15 is the one that works.

## AGGRESSION: size, not trade count (measured 2026-07-29)

Leo asked for the bot to stop playing it safe. Tested both ways on ten months
of US30 15m, full compounding runs on his real balance:

| build | risk | $/mo | ends | trades | PF | drop |
|---|---|---|---|---|---|---|
| **picky NY** | **5%** | **+$1,030** | **$13,155** | 51 | **1.70** | **34%** |
| picky NY | 3% | +$541 | $8,163 | 51 | 1.85 | 28% |
| picky, all sessions | 5% | +$826 | $11,069 | 113 | 1.35 | 40% |
| loose, all sessions | 5% | +$553 | $8,278 | 250 | 1.17 | 65% |

Loosening the touch filter to 2 and allowing four trades per session takes 250
trades instead of 51 -- five times the activity -- and earns LESS at every risk
level while doubling the drawdown. Profit factor collapses 1.70 -> 1.17.

So "be more aggressive" resolves to **bet bigger on his filter, not around it**.
His three-touch rule is doing real work; the trades it refuses are the ones
that bleed. Risk is where the aggression pays, and it keeps paying up to about
5% before 8% starts costing money again.

NAS100 loses at every setting tested and is not a second market for this
strategy. Running both together on one account also loses: 527 trades, -$31 to
-$198/month, up to 96% drawdown.

## His exit management, tested and rejected

He manages winners rather than only waiting for the target: "we can take half
our profit, put stops to break even", "75% of my profit and let the rest run",
"I closed all my position at Target 3."

Built the breakeven-stop half of that and measured it. It is worse on both
axes at every level:

| breakeven at | 1.5% risk | 5% risk |
|---|---|---|
| **off** | **+$219/mo, 18% drop** | **+$1,030/mo, 34% drop** |
| 1R | +$166, 20% | +$765, 39% |
| 2R | +$181, 21% | +$771, 42% |
| 3R | +$161, 23% | +$624, 48% |

Saving the small losses costs the runners that dip before they fly, and at 1:8
the runners ARE the business. Drawdown rises too, because a stopped-out
breakeven trade re-enters into the same move and pays the spread twice.

Kept in the code, off by default -- a human managing one trade with judgement
is doing something a fixed rule cannot copy.

## Small account (~$150 live, leveraged) — what actually applies

**Lot size is not the constraint.** US30's minimum 0.01 lots is $520 of index
needing $10 of margin at 1:50, and a half-candle stop on it risks 0.13% of a
$150 account. There is plenty of granularity; the account can express any risk
level the strategy wants.

**Risk peaks at 5-6%, the same place it peaks on every account size** — so the
ceiling is the strategy's, not the balance's. Ten months of US30 15m:

| risk | growth | per month | worst drop |
|---|---|---|---|
| 3% | 3.1x | +12.1% | 27% |
| 5% | 5.1x | +17.7% | 34% |
| **6%** | **5.2x** | **+17.8%** | **36%** |
| 8% | 4.1x | +15.1% | 47% |
| 15% | 1.5x | +4.2% | 71% |

Past 6% the account compounds through deeper holes and ends smaller. At 15%
it is barely above break-even while drawing down 71%.

**New York alone beats all three sessions again** at the same risk: 5.15x
against 4.19x, half the trades, shallower drawdown. Third independent test
pointing the same way -- his one-session habit is doing work.

**Percentages, not dollars:** roughly +17% a month compounding, with a peak-to
-trough dip of about a third of the account somewhere along the way. That dip
is not a tail risk to be engineered away; it is what a 25%-win-rate, 1:8
strategy feels like from the inside.

## Is 6% risk real, or fitted to these ten months?

Each quarter tested on its own at 5% and 6%: 2.31x, 1.06x, 2.10x, 1.17x. Every
quarter profitable at both, and 6% edges 5% in all four. Not a curve-fit to one
lucky stretch.

## Is it secretly a volatility bet?

Quarters ranged from 47 to 65 point average candles -- a 38% spread -- and all
four were profitable. The two best quarters had the LOWEST and the second
HIGHEST volatility, so returns do not track it.

An artificial test that halved every candle's range did produce a losing
result, but that test is not what it appears: stretching or shrinking wicks
while leaving closes untouched manufactures bars where price wanders without
going anywhere, which punishes any breakout strategy by construction. Recorded
here because the number looked alarming and the honest read is that it was a
bad test, not a bad strategy. The real-quarter evidence is what stands.

## Trying to reach his 2-3 trades a day — four routes, all lose

The bot takes ~0.17 trades/day on US30. He takes 2-3. Every route to closing
that gap was tested and every one loses money:

| route | trades/day | growth | drawdown |
|---|---|---|---|
| **US30 alone (current)** | **0.17** | **5.15x** | **36%** |
| 4 markets, one at a time, NY | 0.48 | 1.65x | 68% |
| 4 markets, NY, concurrent | 0.73 | 3.19x | 85% |
| 4 markets, one at a time, all sessions | 1.03 | 0.28x | 89% |
| 4 markets, all sessions, concurrent | 1.48 | 0.20x | 95% |
| looser filter on US30 (earlier test) | 0.83 | worse at every risk | 65% |
| 5m and 1m timeframes (earlier test) | higher | loses thousands | — |

Each market alone at the winning settings:

| market | growth | win rate |
|---|---|---|
| **US30** | **5.15x** | **25.5%** |
| NAS100 | 0.89x | 16.2% |
| SPX500 | 0.92x | 14.0% |
| GER40 | 0.61x | 12.3% |

**The edge is US30-specific.** The other indices run his exact rules and lose.
So the frequency gap is not timidity in the build -- there are only about five
qualifying setups a month on the one market where the rules work, and
manufacturing more by any means measured so far destroys the account.

What this most likely means: his 2-3 trades a day come from discretion, not
from rules. He looks at a chart and judges which break is real, which level is
worth respecting, when a market is behaving. That judgement is the part of him
a rule engine cannot copy -- and the part that is doing the work in the gap
between 0.17 and 2.5 trades a day.

## His OTHER trade: fading the channel (from a live breakdown video)

Watching him walk through a real trade revealed a second mode entirely, and it
is not a breakout:

    "I started off looking at the H4, and what I saw was a very simple
    channel. Price respected this channel -- boom, boom, boom. We're adding a
    resistance here with these two wicks, and we're also at the top of this
    channel. I believe price is going to crash down and hit the bottom of our
    channel... price will either respect this channel or hit this support, one
    or the other."

So: higher-timeframe channel, wait for price to reach an edge and be rejected
there, take it back toward the far side. Stop just past the edge, target the
opposite side.

**This solves the frequency problem.** A channel edge gets touched far more
often than a level gets broken: 1.16 trades/day against the breakout's 0.17.
That is his stated two-to-three a day, near enough.

**Risk must come down with frequency.** At 6% the drawdown is 83%; at 2% it is
39% for a better return. More trades at a 15% win rate means longer losing
runs, and the size has to respect that.

**But it does not hold up across time.** Quarter by quarter at 2%: 0.89x,
0.98x, 2.61x, 1.06x -- profitable in two of four, and the full-run 3.27x is
carried almost entirely by one strong quarter. The breakout mode, by contrast,
is profitable in four of four at 5.15x.

So the honest position after three hours: his frequency is reachable, and the
mode that reaches it is the one he actually described on video, but it is not
reliable enough to trade on its own. Frequency and consistency trade off
directly here, and the trade is steep.

## Running both his trades together — the best build so far

He has two trades, not one. Teaching videos are all breakouts; the live
breakdown was a channel fade. A market either breaks a level or respects it,
and he has a trade for each -- so running only the breakout half meant sitting
out every session where the range held, which is most of them.

US30 15m, ten months, $150:

| risk | trades/day | growth | quarters up | drop |
|---|---|---|---|---|
| 1% | 1.28 | 2.09x | 3/4 | 25% |
| **2%** | **1.08** | **4.59x** | **3/4** | **44%** |
| 3% | 1.07 | 4.55x | 2/4 | 61% |
| 6% | 1.10 | 7.63x | 2/4 | 90% |

Better than either half alone: the breakout returns 5.15x but trades 0.17
times a day, the channel fade trades often but holds up in only two quarters
of four. Together: near his frequency, three quarters of four, 4.59x.

Breakout takes priority when both fire. Once a level actually breaks, the
channel it belonged to is not a channel any more, and fading its edge is
taking the wrong side of the same event.

## His exit ladder: Target 1, Target 2, Target 3

He does not use one target. "I closed all my position at Target 3." "Target 2
ended up getting hit." "We held this to a one to five, then take all your
profit or put your stops into profit." And on holding: "I don't care what
anybody says about holding trades for a few hours or 8 hours."

Built as a ladder of (R-multiple, fraction) rungs, with the stop advancing to
each rung as its piece is taken -- so the stop position IS the record of which
rungs are done, and nothing needs persisting between scheduled runs.

US30 15m, $150 at 6%:

| exit plan | growth | win rate | drop | quarters up |
|---|---|---|---|---|
| **one target at 1:8** | **5.15x** | 25.5% | 36% | **4/4** |
| T1 2R/50%, T2 5R/50% | 3.96x | **48.5%** | **28%** | **4/4** |
| T1 2R/33%, T2 4R/50% | 4.08x | 48.5% | 28% | 3/4 |
| T1 1R, T2 3R, T3 5R | 3.61x | 61.3% | 29% | 2/4 |

Scaling out trades money for smoothness: the win rate roughly doubles and the
drawdown falls by a fifth, but growth drops by a quarter. Both the single
target and the 2R/5R ladder hold up in four quarters of four.

**This probably explains his record claims.** "500 wins and 20 losses in two
months" is impossible for a single 1:8 target, which wins about a quarter of
the time by construction. Taking a piece at Target 1 converts most trades into
technical wins -- 25.5% becomes 48.5% on the same trades, purely from
bookkeeping. His numbers and his method are consistent once the ladder is
visible; they are not consistent with the strategy as taught in his breakout
videos.

## What HE says about risk, in his own words

Mined from 518,000 characters of his transcripts:

* "Risking 10 percent is not very smart because you've already lost 10 percent
  of your account."
* "Put $100 in an account and risk 30%. Two trades go by, your margin call,
  you're done. You lost everything. With the 5%, 10 trades go by, you've only
  lost half."
* "$50 account, you're risking $5 per trade."
* "Once you start risking $20 per trade, you're making $80 per win" -- a 1:4,
  on a small account.
* On his own scaling: "If normally I'm risking $10,000 per trade, I'm now
  risking only $4,000, and my stop loss is much tighter."

**His stated risk is 5%. He calls 10% unwise and 30% a two-trade wipeout.**

That matters because the independent measurement landed in the same place:
testing US30 15m across $150 to $2,635 accounts, returns peak at 5-6% risk and
fall away above it. Two different methods -- his experience, and ten months of
his own strategy run against real prices -- produce the same number.

So the bot is already sized the way he sizes. The instruction to "go riskier
than he does" is not a way of copying him more closely; by his own account it
is the way to be margin-called.

## Everything of his, together — and the trade-off it exposes

US30 15m, $150, ten months, both trades running with his target ladder:

| build | risk | trades/day | growth | win% | drop | quarters up |
|---|---|---|---|---|---|---|
| both trades, single 1:8 | 2% | 1.08 | **4.59x** | 17.6% | 44% | **3/4** |
| both trades, single 1:8 | 5% | 1.10 | 5.82x | 16.7% | 86% | 2/4 |
| **both + his T1/T2 ladder** | **2%** | **2.01** | 2.12x | **35.3%** | 56% | **3/4** |
| both + ladder | 5% | 1.98 | 3.18x | 37.6% | 91% | 2/4 |

**His trade count is reached: 2.01 a day.** The ladder roughly doubles trade
frequency, because taking a piece at 2R frees the position for the next setup
instead of holding one trade to 1:8.

And that is exactly why it earns less. 4.59x becomes 2.12x. The 1:8 runners
are what pay for a 17% win rate, and scaling out caps them -- the win rate
doubles to 35% while the money halves. Every mechanic of his that makes the
equity curve *feel* better costs return.

So the honest summary of copying him completely: the frequency is his, the win
rate is close to his, the drawdown is real, and the money is lower than the
simplest version of his own strategy. More of him is not more money.

## How long to hold — measured, 2026-07-29

Leo asked what happens if a trade is only held 20-30 minutes. Testing it
exposed a bug that had been quietly disabling every time-based rule in the
backtester: simulated positions were stamped with the real wall-clock date, so
`now - opened_at` came out around minus 300 days. A hold limit tested as a
perfect no-op across seven settings, which reads like "holding time doesn't
matter" rather than "the feature never ran". Same bug meant the channel half's
"max 3 trades a day" cap had never been enforced in any backtest, and the
breakout's same-session guard was always true.

With the clock fixed, on $150 at 6% risk, US30 15m, 10 months:

| hold cap | growth | trades/day | win% | worst drop | quarters up |
|----------|--------|-----------|------|-----------|-------------|
| 20-30 min | 2.10x | 1.30 | 47.7% | 53% | 3/4 |
| 1 hour | 5.09x | 1.09 | 46.9% | 46% | 4/4 |
| 2 hours | 8.55x | 0.90 | 45.5% | 52% | 4/4 |
| **3 hours** | **11.93x** | **0.87** | **41.7%** | **46%** | **4/4** |
| 4 hours | 9.97x | 0.87 | 41.4% | 46% | 3/4 |
| no cap | 11.05x | 0.52 | 28.7% | 55% | 4/4 |

**His own words argue against a short hold and the numbers agree**: *"I don't
care what anybody says about day trading in terms of holding trades for a few
hours or 8 hours or whatever."* A 20-30 minute cap cuts the 1:8 winners off
before they arrive — the win rate climbs to 48% because small gains get banked,
but the few big runs are what pay for everything, and capping them costs 80% of
the return.

**But the test found the real reason bot 2 only trades 0.52 times a day**, which
is the thing Leo has been asking about for hours. It is not the entry filters.
A trade held to target stays open about **10 hours**, and the risk layer allows
one position per symbol, so every signal that fires while it is open is refused.
Holding less long is how the frequency goes up.

**Honest caveat on the 11.93x.** Per quarter, each starting fresh from $150, the
cap is *worse* in three quarters of four (1.44/2.34/1.45/1.18 against
1.44/2.83/1.76/1.57). The full-run edge is a compounding-path artifact, not a
per-period gain. What survives that check is the trade count, the win rate and
the drawdown — at 5% risk the cap drops 39% against 47%, at 2% it drops 16%
against 25%. So the cap is registered for frequency and smoothness at roughly
equal money, not for more money.

Neighbours from 150 to 225 minutes all come out 8.9x-11.9x and 4/4, so this is a
plateau rather than a spike; 180 sitting on top of it is partly luck. The 75
minute setting collapsing to 2.31x and 2/4 between two healthy neighbours is a
reminder of how noisy this surface is.

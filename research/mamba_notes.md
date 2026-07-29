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

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


### Correction, same day: the hold-time table above was measuring nothing

Leo asked for proof of the numbers and the first thing the raw trade list showed
was trade 1 held 570 minutes and trade 6 held 1425 minutes -- under a "180
minute cap". The cap had been placed *after* MambaBreakout's session gate,
which returns early outside New York hours, so it could only fire during the
session. What was committed as "a 3 hour cap" actually behaved as "close stale
trades whenever New York next opens".

With the check moved above the gate and genuinely enforcing itself:

| hold cap | growth | trades/day | win% | worst drop | quarters up |
|----------|--------|-----------|------|-----------|-------------|
| 30 min | 1.12x | 2.28 | 45.7% | 60% | 2/4 |
| 1 hour | 2.46x | 1.73 | 49.9% | 53% | 3/4 |
| 2 hours | 2.48x | 1.30 | 47.9% | 47% | 3/4 |
| 3 hours | 0.97x | 1.20 | 45.5% | 69% | 2/4 |
| 8 hours | 2.26x | 0.96 | 38.4% | 67% | 2/4 |
| **no cap** | **11.05x** | **0.52** | **28.7%** | **55%** | **4/4** |

So the answer to the original question reverses completely. **Every cap is much
worse than none**, and a real 3-hour cap loses money (0.97x). The 11.93x that
justified registering it was an artifact of the bug. Reverted to no cap.

This is the third time in this project that a rule which appeared to help was
actually a rule that never ran: `2h` missing from the timeframe table, the
wall-clock stamp disabling every time-based rule, and now an exit placed behind
an entry gate. The pattern worth remembering: **a parameter sweep where the
setting does nothing produces a smooth, plausible table**, and the giveaway is
always in the raw per-trade output, never in the summary.

Note also that a 30-minute cap does reach 2.28 trades a day -- inside Leo's
stated 2-3 -- at 1.12x. So his frequency target is achievable; it just costs
about 90% of the return. The tension is real and unresolved.

---

## CYCLE 1 of 15 — "$100 Forex Account TRADING STRATEGY | EASY" (I_33XcywuIo)
Watched: full audio transcript + 33 frames at 1024px, including the drawn charts.

This is the single most relevant video in the catalogue for a $150 live account,
because it is explicitly built for one. It also contradicts three things I had
already built, and under RULE ZERO his version wins.

### What he actually does, quoted

**1. Higher timeframe first, mark the zone.**
> "first thing you're gonna do is pretty much turn the higher time frame so
> right here I'm looking at the four hours I'm gonna mark up a zone... price has
> made large rejections to the upside"

**2. Wait for the zone to be retested by a WICK before you look for anything.**
> "price has actually came back retested it with a wick once we saw this wick
> that's when we'd start looking for sales"

**3. A small account must NOT trade the higher timeframe.**
> "we're not gonna look for sales on the for our because you know obviously
> we're using a hundred dollar count we can't really trade the for our because
> you know our stop losses are gonna be too high we're gonna lose too much money"

**4. RISK, in his own words — this is the answer to how much to risk:**
> "we don't want to risk more than you know three to five percent max right"

**5. Drop to M15 to enter.**
> "so now what are we gonna do it's going a 15-minute time frame... this is the
> 15-minute chart right here you're gonna get your best entries especially with
> a smaller account"

**6. THE ENTRY IS A BREAK AND RETEST — not the break itself.**
> "price broke below these loaves came back and as you can see retested it"
> "this is pretty much just like a break and retest strategy it's very simple"
> "we get in a short position off that wig"

**7. Stop goes just past the level, because past it the idea is dead.**
> "stop-loss just in the middle or just above this little support zone because
> if it breaks above this support so we don't even want to be into anyways"

**8. Target is the NEAREST previous structure, not a fixed multiple.**
> "I would target this zone right or this sound but I would stick from now to
> this zone cuz it's the closest and you see a major wick rejection"

**9. His actual numbers, spoken and confirmed on screen:**
> "22 pips stop-loss with a 50 80 take profit it's beautiful numbers"
> "16 pips stop-loss 51 pivot a profit"

Measured off the drawn boxes in the frames: example 2 has a red risk box of
~17 pips against a green reward box of ~52 pips. **1:3.** Not 1:8.

**10. Lot size and the losing-streak logic.**
> "if you're using a 0.01 that would have been a dollar sixty loss for a five
> dollar and 10 cent gain right so you can lose to three trades in a row and
> then win one and you're still gonna be positive"

**11. Visible on his chart but never mentioned:** SMA 8, 50, 100, 150, 200, 250,
300, 400, 500, 600 all loaded. He never refers to them in this video. Noted, not
built -- building an unmentioned indicator would be inventing, not copying.

### Where this contradicts what I had built

| my build | what he actually does |
|----------|----------------------|
| reward 1:8 fixed | **1:3, and the target is the nearest structure** |
| enter ON the break, intrabar | **enter on the RETEST of the broken level** |
| 6% risk | **"three to five percent max"** |
| stop = half the breakout candle | **stop just past the level** |

Under RULE ZERO all four change to his version. Building `mamba_retest.py`.

Note for the record, not as a veto: 1:3 with his ~40% win rate is a smaller edge
per trade than 1:8 at 29%, but a retest entry fires far more often than a break
entry, which is the direction Leo wants (2-3 a day). Tested numbers to follow.

### Built and measured: `mamba_retest.py`

His geometry reproduces faithfully. At the default zone the realised stop is
**0.12% of price** against his 0.11% (16-22 pips on a 1.40 pair), and the
realised reward is **3.0R** against his stated "22 pip stop with a 50-80 take
profit". So the trade the code takes is the trade he draws.

On one market at 5% risk (his ceiling), 10 months:

| market | growth | per month | trades/day | win% | drop | quarters up |
|--------|--------|-----------|-----------|------|------|-------------|
| EURUSD | 1.48x | +4.0% | 0.26 | 41.5% | 26% | 3/4 |
| GBPUSD | 1.35x | +3.1% | 0.28 | 26.7% | 36% | 4/4 |
| AUDUSD | 0.61x | -4.8% | 0.30 | 22.9% | 51% | 2/4 |
| US30 | 1.42x | +3.5% | 0.45 | 25.0% | 59% | 2/4 |

### THE FREQUENCY PROBLEM IS SOLVED, AND HIS WAY

One market gives 0.26-0.45 trades a day. **He does not watch one market.** Six
markets at once, same rules untouched:

| risk | growth | per month | trades/day | win% | drop |
|------|--------|-----------|-----------|------|------|
| 3% | 1.57x | +4.6% | **1.85** | 28.2% | 58% |
| 5% | 2.61x | +10.1% | **1.99** | 27.9% | 81% |

**1.99 trades a day is inside his stated two-to-three**, and it took no loosening
of any filter he named -- same touch count, same retest requirement, same stop,
same target, same 3-5% risk. The only thing added is the one difference Leo
allowed: the bot watches every market at once, which a human with two kids and a
camera to run cannot.

This is the first route to his frequency that did not require breaking one of
his rules. Every earlier attempt (looser touches, faster timeframe, more trades
per session, hold caps) bought frequency by weakening the setup. Scanning more
markets buys it by doing more of the same work.

Honest on the money: 2.61x over ten months is well below mamba_both's 11.05x, and
the 81% drawdown at 5% is worse than anything else registered. At 3% the drop is
58% for 1.57x. So copying him exactly, on his own numbers, at his own risk
ceiling, currently returns less than the 1:8 breakout build. Recorded, not acted
on -- RULE ZERO says his way stands. What it needs next is more of his videos on
which markets he actually scans and what he skips, not a parameter I invented.

---

## CYCLE 2 of 15 — four videos, captions mined for the open questions
hGPg7_ZE1DM "COMPLETELY FREE DAY TRADING COURSE", prtpGhzb22g "6 Tips To Become
a PRO SCALPER", dCCVN-0cqH0 "$62,000 scalping forex LIVE", 9bPlk7zSJAI "$1400 in
2 hours SCALPING CRYPTO".

### WHICH MARKETS HE ACTUALLY TRADES — answered outright

> "i'm actually going to be full time trading just **nasdaq us 30 gbp usd** and
> all of my **cryptos** and that's going to be it for now when i'm done trading
> all the regular 4x pairs i'm done"

So the watchlist is NAS100, US30, GBPUSD and crypto -- and he is explicitly
DROPPING the rest of forex. My six-market portfolio test included EURUSD, USDJPY
and XAUUSD, none of which he trades. That is not copying him.

### HIS REAL TRADE FREQUENCY AND WIN RATE — from his own mouth

> "the last month or so i've taken about **30 trades** i lost four of those right
> so i think i went **26 wins four losses**"

30 trades a month is **~1.4 a day**, not 2-3. And he claims 87% winners on a
month he calls "a really really really good month". My retest build at 1.85-1.99
a day is running ABOVE his actual rate. Correcting toward him means fewer trades,
not more -- which reverses the direction I have been pushed all session.

He is also explicit about the ceiling:
> "you cannot go out there and take **30 trades in one night** you just can't you
> don't want to do that you don't want to mess with your psychology that much"

### THE CONFLUENCE RULE — stricter than what I built

> "we cannot take these five-minute trades if our **h4 or our daily** is not in
> confluence telling us we're going down"

Two higher timeframes, not one. And the entry timeframe here is the **5-minute**,
not 15.

### THE 50 MOVING AVERAGE — first indicator he names

> "as we start to trade **below our 50 moving average** we could see potentially
> all cryptos across the board continue to drop"

In cycle 1 I logged SMAs 8/50/100/…/600 visible on his chart and deliberately did
not build them because he never mentioned them. He mentions the 50 here, as a
directional signal. That clears the bar: build it.

### TRAILING STOP — confirmed

> "very tight stop loss huge take profit i'm going to **trail my stop-loss all
> the way up** i'm gonna make a lot of money right and that's how i'm trading"

### TAKE PROFIT LADDER — confirmed again

> "so **take profit one take profit two** hit came back up and then again you know
> i took my profit already on that drop"

### STOP PLACEMENT, restated

> "because this is a major bullish candle to me boom so i'll take my long position
> off of that candle i have my **stops pretty much just below** because if price
> breaks back down here most likely it's going to continue down and then i will go
> ahead and zoom out and i'll **target my next main zone**"

### HIS R:R ON THE BIG ONE

> "this is a thousand pip trade **250 pips stop loss a thousand pip take profit**
> that's the game"

1:4. Together with the $100-account video's 1:3 and the 1:8 I had built, his real
range is **1:3 to 1:4**, chosen by where the next zone sits.

### Retest applies to supply/demand too, then breaks out

> "same thing with supply and demand price will come back **re-test** supply demand
> whatever the case may be if you're going up or down and then it will **break
> out**"

### What changes in the build

1. Markets: NAS100, US30, GBPUSD, crypto ONLY. Drop EURUSD/USDJPY/XAUUSD.
2. Add the 50 MA as a directional filter -- he named it.
3. Add a trailing stop -- he says he trails all the way up.
4. Two higher timeframes must agree (H4 and daily), not one.
5. Target 1:3-1:4 via nearest zone, already built in cycle 1.

### Cycle 2 build results — his 3 markets, 5% risk, 15m, 10 months

| build | growth | trades/day | win% | avg win | drop |
|-------|--------|-----------|------|---------|------|
| cycle 1 (no MA, no trail) | 2.06x | 1.02 | 26.5% | — | 66% |
| **+ his 50 MA** | **2.13x** | 0.96 | 28.0% | 2.7R | 62% |
| + daily confluence | 1.06x | 0.69 | 26.8% | — | 76% |
| + trail 1R | 1.09x | 1.05 | 40.7% | 1.3R | 59% |
| + trail 2R | 1.50x | 0.98 | 35.0% | 1.8R | 56% |
| + trail 6R | 1.95x | 0.96 | 28.4% | 2.6R | 56% |
| everything he named | 0.70x | 0.72 | 33.5% | — | 73% |

**The 50 MA earns its place** — better money, fewer trades, smaller drop. Built.

**The trail needs care, and the reason is a gap in what he said, not a
disagreement with him.** He says "very tight stop loss huge take profit i'm going
to trail my stop-loss all the way up" but never says how far behind. That distance
is therefore mine to invent, and inventing it tight contradicts the same sentence:
a 1R trail turns his 2.7R average winner into 1.3R and the win rate jumps to 41%,
which is the signature of banking winners early -- the opposite of "huge take
profit". Registered at 6R, which sits beyond every target he draws, so it only
manages a trade that has already run past its zone. That is the situation the
quote describes.

**The daily confluence is off, and this is an admission not an override.** He says
"h4 or our daily" must agree. I implemented "daily" as position within a 384-bar
range, which is a guess, and it costs 2.13x -> 1.06x. The failure is most likely
my stand-in rather than his rule. Left as a parameter, defaulted off, flagged: need
a video with the daily chart actually on screen before this can be built faithfully.

**Frequency:** 0.96/day on his three markets against his own stated ~30 trades a
month (~1.4/day). Closer to him than the six-market version's 1.99, and six markets
included EURUSD, USDJPY and XAUUSD -- pairs he says he has quit. Dropping them is
more faithful even though it lowers the trade count.

---

## CYCLE 3 of 15 — 22 transcripts mined at once

Background harvester now running continuously so material is always waiting.

### NEW YORK SESSION ONLY — and the exact clock time

> "The first thing being is **you only trade during New York session**."
> "you trade during New York session open, which is around **6:20, 6:30 a.m.**"
> "With New York session, **6:30 every morning is always the time to trade** and it
> does a lot psychologically and then just in general like I said you're going to
> find good setups because of **volume** every single morning."

6:30 a.m. is his local clock, and 6:30 Pacific is 9:30 Eastern is **13:30 UTC** --
which is exactly the `newyork` open already in SESSION_OPENS_UTC. That setting is
confirmed rather than guessed now.

And an exception, for gold specifically:
> "New York session's okay, but **Tokyo session for me is better for gold**."

`MambaRetest` had no session filter at all. That is a miss, not a choice.

### PARTIALS — the most explicit he has been

> "so now we're currently probably about 30 pips profit **might even put my stop
> losses to break-even here** just to uh just just to be safe and I'm gonna secure
> profit still **I'm gonna take half my profits here**"

> "this is kind of spots where we're either going to **stops to break even here take
> half our profit here** and take the rest of our profit or all of our profit here
> that's a way to look at it or like i did take all my profit here because it's 700
> pips and i'm happy with it"

So both mechanics, together: **stop to breakeven AND half off** at an intermediate
point, then let the rest run. I tested both earlier in the project and both cost
money -- breakeven took $1,030/mo to $765, scaling out took 5.15x to 3.96x. Under
RULE ZERO they go in anyway, because he says he does them.

### STOP PLACEMENT — structural, not candle-based

> "**Obviously, stops are right above the highs.**"
> "My stop loss is going to go **below the low** with five micros of this previous...
> Let's do the low right here **to the left**."
> "**Stop loss is going to go above the highs** and that's it for me."

The stop sits beyond the swing high or low to the LEFT of entry -- past the
structure, not a fraction of the entry candle. `MambaBreakout` uses half the
breakout candle, which is my invention. His is structural.

### H4 IS ALWAYS THE STARTING POINT — said three more times

> "we're gonna **start on the h4** and we're simply going to look for support or
> resistance"
> "so let's go to our **h4** and let's look for another setup that i took on **nas 100**"
> "if we go down to our **h4** and we look for more confluence"

### DONE FOR THE DAY

> "**Close the position and we're done for the day.**"

### Fibonacci as extra confluence, and an optional tool

> "we even might have another **Fibonacci** test from here to here we may have
> another one right there just just being confluence"

> "I'm not saying that you need it **you can be very successful without it in fact
> I've been very successful without it my entire career** but now this is just
> giving me more Confluence and making it a lot easier to trade"

That last one is him explicitly marking a tool as optional. Whatever it is (video
oHV2PlHj-aM) does not go in the core -- he says his whole career ran without it.

### Build queue from this cycle
1. New York session filter on MambaRetest (13:30 UTC), Tokyo for gold. MISSING.
2. Breakeven move + half off at an intermediate target. He says both.
3. Structural stop: beyond the swing high/low to the left, not a candle fraction.

---

## CYCLE 4 of 15 — "How I Make 20% Gains Daily Trading Futures" (-VdyJZlCG1M)

The single most useful video so far. It settles the session question, gives the
exact trading window, and **reverses what I told Leo about hold time**.

### The session rule applies to indices, by his own statement

> "The first thing being is **you only trade during New York session**. Okay? you
> trade during New York session open, which is around **6:20, 6:30 a.m.** **Just
> like I say with indices, it does the same thing during the same time.** You're
> going to get the same movements. And literally, there's actually **almost no
> difference at all** when it comes to trading futures and the times"

So this is not a futures-only rule. It covers US30 and NAS100. It stays.

### THE EXACT WINDOW — 6:30 a.m. to 10:00 a.m.

> "It's already almost **10:00 a.m. I don't like to trade much past 10:00 a.m.**,
> so that's the main reason that I'm kind of done here. **I don't want to sit here
> and freaking trade all day and trade into the evening.** It doesn't make a lot of
> sense."

6:30 to 10:00 Pacific is **13:30 to 17:00 UTC** -- a **210 minute** window. My
tested widths of 240, 390, 480 and 600 minutes were all guesses, and all too wide.
210 is his number.

### HOLD TIME — I OWE LEO A CORRECTION

> "You know, you get in, you get out, you move on. **You don't hold trades for a
> long time. You get in, you get out, and you move on.** It's as simple as that."

> "Mind you, we've been trading for currently **30 minutes, 35 minutes at the
> most**. Not very long."

Leo asked "what if u held a trade for 20-30 minutes" and I answered that capping
the hold was bad, quoting him saying "I don't care what anybody says about holding
trades for a few hours or 8 hours or whatever". **Leo was right and my answer was
built on the wrong quote.** On this method he holds about half an hour and says so
twice. The earlier quote came from a different context; this one is him narrating a
live trade with a clock running.

Why my test disagreed: I capped the hold on the **1:8** breakout build, where a
target eight times the stop genuinely needs hours to arrive. His target is **1:3**,
which arrives in about thirty minutes. The cap only looked harmful because it was
bolted onto a target he never uses.

### His reward, stated three more times

> "we can go for a nice little **one to three**"
> "We could have probably got a **1 to five** there"
> "Got about a **1 to three**. Could have gotten a little more. Maybe even got close
> to a 1 to 5, but again, **I closed a little early**"

### He closes early and is fine with leaving money behind

> "this thing ended up breaking past the resistance and flying. I could have made
> more money. **I actually left some money on the table there, but I'm okay with
> that.** 20% gains."

### Levels do not have to be clean

> "I like the support zone because you got a couple touches in here, touches up
> here, touches down here. **It's not perfect. Resistance and support lines do not
> need to be perfect.**"

Two touches is enough. My min_touches of 3 on MambaBreakout is stricter than him.

### The setup, in order

> "there's only **two things** we're looking for. We're looking for a **break of a
> support or a break of resistance**, but we also want to **pair that with which way
> is the market moving currently**."

> "we see price is bullish. We're breaking out of previous lows... That tells me
> we're probably going to want to look for buys. Now, if we're going to look for
> buys, we need to see a **resistance or a trend line break**."

### Timeframes for entry: 5 minute for the level, 1 minute for the trigger

> "we have support on the **5 minute chart**... Now, all we had to do go to the
> **1 minute** if you want to. We can find a **break of a trend line** right here.
> We push above the trend line and now we're buying."

### He refuses trades into strong opposing structure

> "It's a pretty good position though, but **we're at a pretty strong resistance
> here. So, no, not the smartest trade.**"

### And his daily number, on a real account

> "$349, 350 bucks on a **2K account**" -- about **17.5% in 30-35 minutes**, which
> he rounds to "20% gains" for the day and says "Tomorrow, I'll do it again."

### Cycle 4 test results, and a data limit worth stating

His 210-minute window on 15m bars, his 3 markets, 5% risk:

| build | growth | trades/day | win% | median hold | drop |
|-------|--------|-----------|------|-------------|------|
| no session (cycle 2) | 1.95x | 0.96 | 28.4% | 90m | 56% |
| his 210-min window | 0.74x | 0.26 | 20.7% | **30m** | 52% |
| + hold cap 35 min | 0.93x | 0.29 | 31.7% | 30m | 34% |

**The median hold came out at 30 minutes on its own**, without a cap, once his
session window was applied -- matching "30 minutes, 35 minutes at the most"
exactly. That is a strong sign the window is right even though the money is not.

Why the money is not: **his session method does not run on 15-minute bars.** A
210-minute window is only 14 bars of 15m, which is not enough to find a level and
its break. He says the timeframe out loud -- "we have support on the 5 minute
chart... go to the 1 minute". Data on hand: US30_5m and NAS100_5m cover 2026-04-17
to 2026-07-29 (3.5 months, 20000 bars), US30_1m covers 6 weeks. Shorter than the
10 months used everywhere else in this file, so results from it are weaker evidence.

### And the setup he narrates is NOT the retest -- it is a break

> "there's only **two things** we're looking for. We're looking for a **break of a
> support or a break of resistance**, but we also want to **pair that with which way
> is the market moving currently**."

> "**If price can break past that wick again, I'm going to take a buy position.**
> 100% going to take a buy position. Okay, we can go for a nice little one to three."

So he has (at least) three distinct trades, and I have now seen all three:

1. **Break and retest** -- the $100 forex account video. `mamba_retest.py`.
2. **Channel edge fade** -- the live H4 breakdown. `mamba_channel.py`.
3. **New York session break** -- this video. Level with a couple of touches, price
   breaks it, current market direction agrees, 1:3 target, 5-minute chart,
   6:30-10:00 a.m. only, held about half an hour. NOT YET BUILT as its own file --
   `mamba.py` is the closest but uses 1:8, a candle-fraction stop, 3 touches and no
   time limit, all of which are mine rather than his.

Next: build #3 properly as `mamba_ny.py` on 5-minute bars.

### Cycle 4-5: `mamba_ny.py` built, and a fourth silent-rule bug found

`mamba_ny.py` is his New York session break: level with two touches, price breaks
it, current direction agrees, structural stop, 1:3 target, 13:30-17:00 UTC only,
held about 35 minutes. On 5m data (3.5 months, all that exists) at 3% risk it runs
US30 0.63x and NAS100 1.16x. Weak, and the sample is short.

**But building it exposed the worst bug in the project so far.** MambaNY was taking
4.4 trades a day through a cap set to 3. Two causes, both the same shape as the
clock bug from earlier today:

1. `_trades_today` counted OPEN positions. A closed trade vanishes from that list,
   so "max 3 trades a day" actually meant "max 3 open at once". Present in
   `mamba_channel` and `mamba_retest` too -- so **his stated 2-3 a day has never
   been enforced in any test in this file.**
2. `run_backtest` never called `risk.update_equity` at all, so `RiskState.current_day`
   stayed empty for entire runs. That disabled everything keyed to a day: the
   per-strategy trade counter never reset, **and the daily-loss breaker never armed
   in a single backtest ever run on this project.**

Fixed: RiskState now carries `trades_today` per strategy, `Enter.execute` records it,
both backtest loops roll the day over on simulated time, and all three strategies
read the real counter. Regression test spans four days and asserts one trade per day
rather than one per run.

Re-measured afterwards on US30 15m at 6%, 10 months:

| build | growth | trades/day | win% | drop |
|-------|--------|-----------|------|------|
| mamba_both | 11.05x | 0.52 | 28.7% | 55% |
| mamba | 5.15x | 0.23 | 25.5% | 36% |
| mamba_channel | 1.28x | 1.24 | 15.0% | 83% |

The headline 11.05x survives the fix. mamba_channel's per-day cap now binds for the
first time and it is much worse than previously recorded -- 1.28x against 4.59x,
because the old number came from a cap that was never applied.

**Fourth instance of one pattern**: `2h` missing from the timeframe table, wall-clock
position stamps, an exit behind an entry gate, and now a calendar that never advanced.
Every one produced plausible numbers. The tell is always that a rule which should
change behaviour changes nothing.

---

## CYCLE 1 of 2 (20-minute run) — "How To Trade SMALL Forex Accounts Using the 1 Minute Timeframe" (5cnHDWQkwLg)

Live session, gold, 1-minute chart, $500 account. Narrated as it happens.

### HE ADDS TO POSITIONS — doubles up when confident

> "well let me do two yep there it is **we're doubling up on that position** by the
> way **I'm pretty confident** we're going to push out here"

Not built anywhere. Building it.

### HIS RESULT THAT SESSION, and his real short-timeframe frequency

> "a **$41 win a $40 win and a $44 win with only $115 loss** turning our **$500
> account into $600** in the span of I don't know it's been like what what would you
> say 30 minutes or so an hour 30 minutes about **30 minutes**"

**+20% in about 30 minutes, four trades.** On the 1-minute he trades far more often
than the two-to-three a day he quotes for indices. Two different tempos for two
different timeframes.

### 1-MINUTE TRADES MUST BE TAKEN QUICKLY — his words on hold time again

> "with these **one minute trades you got to get in you got to get up quick** it's
> not going to be something that lasts you're not going to get in and you're not
> going to watch it just drop and drop and drop **they're reversing and they reverse
> fast** you got to try to maximize your gains"

### TARGET IS THE NEXT STRUCTURE

> "we will go ahead and wait **Target these next highs**"
> "I want to **Target these highs up here** because I truly do believe that's where
> we're going to go"

### GOLD, ON THE 1 MINUTE, IN THE EVENING

> "we're currently on the **1 minute time frame on gold** we are coming to a support
> Zone"
> "this could be our **final trade of tonight** and we'll come back tomorrow"

Evening US time is the Tokyo session, which matches "Tokyo session for me is better
for gold" from the other video. Consistent.

### HE STOPS WHEN THERE IS NOTHING THERE

> "we'll take a couple more final trades **if they are there if not then that's it**"

### Cycle 1 results — NAS100 5m, 3.5 months, 3% risk

| build | growth | trades/day | win% | hold | drop |
|-------|--------|-----------|------|------|------|
| his entry/exit rules only | 0.61x | 2.50 | 38.5% | 35m | 53% |
| + doubling up at 1R | 0.61x | 2.50 | 38.5% | 35m | 53% |
| + breakeven at 1R | 0.56x | 35.4% | | 35m | 54% |
| + half off at 1.5R | 0.68x | 2.81 | 45.9% | 30m | 55% |
| + skip into strong structure | 0.40x | 1.98 | 28.5% | 20m | 61% |
| everything he says he does | 0.33x | 1.96 | 25.9% | 15m | 67% |

Registered `mamba_ny` with everything on, and `mamba_ny_plain` with entry and exit
only. Trade frequency is 1.96-2.81 a day, inside his stated two-to-three, and this
is the first build where that cap is genuinely enforced rather than silently absent.

---

## CYCLE 2 of 2 (20-minute run) — his risk numbers, and what he does after a loss

### RISK — he says 10%, 15%, 25%, and names 30-60% for small accounts

From "The BEST Small Account Strategy NOBODY Tells You" (4JDL4LkFay0):
> "I don't mind going and **risking 15%** on the next trade."
> "I don't mind going and **risking 10%** on the next trade."
> "You may **blow your account** trying for the first few times, but that's okay."

From "How to Make $5,000 in 3 WEEKS Trading FOREX" (M5qKSVhjtQg):
> "let's say you have your $1,000, you want to **risk 25% of your account**, which is
> **kind of what you're going to have to do** if you want to make $5,000 in 3 weeks."
> "if you're **risking 250 out of 1 to 5**... You're risking 250 bucks, which is 25%
> of your $1,000 account, but you're going for a $1250 win every single time"

From "This Candlestick Pattern Changes EVERYTHING" (Xyb8rdUYOW8):
> "when I see this pattern here, **I feel better about risking more** and I know a lot
> of the **textbook traders are going to say, well, never risk more**."
> "A lot of you guys want to get on there and **risk 30% on one trade**, and now that
> you see this, you're going to **risk 60%**."

**Leo asked about risking a third of a small account and I told him it was wrong.
He was right and I was not.** The 3-5% figure came from the $100 forex video; on a
small account he wants to flip fast he names 10%, 15%, 25% and talks about 30-60%.
He is explicit that it is what you have to do to grow a small account quickly, and
explicit that you may blow it.

### AFTER A LOSS — answered

From "How To INSTANTLY Become Profitable Day Trading" (U8nlmxICJwQ):
> "If the second one doesn't work out, **we are done for the day and we come back
> tomorrow** and we do it again."

From "First to get Funded WINS $50,000 CASH" (KD4SjH5zspY):
> "**Close the position and we're done for the day.**"

**Two losses ends his day.** Built as `max_losses_per_day=2`, counting closed losing
trades from the risk layer.

And on revenge trading, from vcLKxGb5bUM:
> "You're going to **revenge trade**, you're going to get angry, you're going to trade
> as hard as you can, and that's not good for you either."

### REWARD — 1:3 to 1:5, stated again

> "**Risk 16 points** on this trade, but shoot for **52 points** up to even **80
> points** on the win." (16 to 52 is 1:3.25; 16 to 80 is 1:5)
> "risking 250 out of **1 to 5**"

### Numbers, NAS100 5m, 3.5 months, reward 1:5

| risk | no loss limit | 2 losses = done |
|------|---------------|-----------------|
| 3% | 0.56x | 0.57x |
| 5% | 0.46x | 0.46x |
| **10% (his)** | 0.19x | 0.21x |
| **15% (his)** | 0.25x | 0.26x |
| **25% (his)** | 0.35x | 0.34x |

His two-loss rule improves every risk level it touches. Built and on by default.

---

## CYCLE 1 of 2 (second 20-min run) — "The BEST Small Account Strategy NOBODY Tells You" (4JDL4LkFay0)

Read off the pixels as well as the audio. This is his complete small-account flip
method and it is the most directly relevant video in the catalogue to a $150 live
account.

### WHAT IS ACTUALLY ON HIS SCREEN (measured from the frame)

* Chart is **US30**, on the **5m** (the 1m/5m/15m/30m/1h/4h/D bar is visible, 5m active).
* Levels are drawn as **thick purple horizontal BANDS**, not lines. Three stacked at
  once: ~49,411-49,430, ~49,340-49,355, ~49,290-49,300. Band thickness is roughly
  15-20 points on a 49,400 price -- **0.03-0.04% of price**, which matches the
  `zone_pct=0.0004` already in the code. Pixel-confirmed rather than guessed.
* A **white descending trendline** drawn from the swing high across the highs.
* His watchlist, titled "Scalping BIG…", reads: **XAU (gold), LTC, FIL, BTC, ETH,
  XRP, NAS100, US30**. That is his stated "nasdaq us 30 gbp usd and all of my
  cryptos" plus gold, confirmed on screen.
* Clock on the chart: entry area around **05:45-06:30**, matching "I love to trade
  at 6:30 a.m."

### HE DRAWS THREE THINGS, AND TRADES THE BREAK OF ANY OF THEM

> "As you can see, I pretty much **drew up my resistance, I drew up my support, and
> I drew my trend line**."
> "we have support, we have our trend line. **If we can break this trend line**, have
> pretty decently aggressive move to the upside, **break past the support**, I think
> it's a really good buying opportunity."
> "we're getting in **as soon as this trend line or the support zone breaks**"

**The trendline is not built anywhere.** Building it.

### VOLUME IS A CONDITION

> "the reason I love to trade at 6:30 a.m., you're going to see a lot of **volume**"
> "The biggest key here, **we're waiting for volume to come in**, and we're getting in
> as soon as this trend line or the support zone breaks."

Not built. Building it.

### TIMEFRAME, STATED OUTRIGHT

> "It's very important that you use a **5-minute or 1-minute chart** simply because we
> are **super scalping**."

### STOPS

> "here's the key with the strategy, **super, super tight stop losses**."

### REWARD FOR A SMALL ACCOUNT — 1:7 to 1:10, NOT 1:3

> "when I want to **flip a small account, I have to go for higher and higher risk
> rewards** and it may seem crazy, it may seem awful, but trust me, it's not as hard
> as you think."
> "We have a **fat one to seven, one to 10** risk to reward."

**The 1:8 I originally built was right for a small account.** I replaced it with 1:3
after the $100 forex video and the futures video. Both numbers are his -- 1:3 is his
normal trade, **1:7 to 1:10 is specifically what he uses to flip a small account**,
which is Leo's situation.

### RISK ON A SMALL ACCOUNT — 25%, and expect to lose it

> "we're **risking $5, which is 25% of the account**, but if we win, we've now turned
> our $20 account into a $55 account, putting us in a much better position."
> "**Deposit as little as $20** and start flipping your account."
> "the reason we use such a small account like a $20 account because **if we do lose
> it, that's okay, we deposit again**."
> "You lose three, four, five at $20, you might lose 100 bucks, but by the time you
> actually can flip it to 1,000, 2,000... none of that will matter."
> "I don't mind going and **risking 15%** on the next trade." / "**risking 10%**"

$5 risk on $20 to a $55 account is a 1:7 win at 25% risk. Consistent throughout.

### AND WHAT HE DOES ONCE IT IS BIG

> "that means you **leave this account, you do 5% per week**, you can go trade other
> accounts, get more risky on these, get prop firms, do whatever you want."

So the plan is two-phase: flip a small account at high risk and high reward, then
drop that account to 5% a week and flip a new small one.

> "when you're flipping small accounts, you want to make sure your **first few trades
> are Ws**"

### Build queue
1. Trendline break entry -- he draws one every time and names it as a trigger.
2. Volume condition -- "we're waiting for volume to come in".
3. Reward 1:7-1:10 for the small-account mode.

### Cycle 1 numbers — US30 + NAS100 5m, 3.5 months, 5% unless stated

| build | growth | trades/day | win% | drop |
|-------|--------|-----------|------|------|
| US30 zones 1:3 | 0.88x | 2.46 | 41.3% | 47% |
| US30 zones 1:7 (his flip R:R) | 0.72x | 2.40 | 38.9% | 48% |
| US30 + trendline break | 0.70x | 2.40 | 38.3% | 44% |
| US30 + trendline + volume | 0.72x | 1.11 | 34.6% | 40% |
| US30 his flip at 25% risk | 0.42x | 0.92 | 35.8% | 64% |
| NAS100 zones 1:3 | 0.53x | 2.32 | 40.2% | 65% |
| NAS100 + trendline + volume | 0.64x | 0.47 | 26.5% | 39% |
| NAS100 his flip at 25% risk | 0.67x | 0.47 | 26.5% | 52% |

Registered as `mamba_flip`. His volume condition cuts the trade count roughly in
half and lowers the drawdown on both markets.

---

## CYCLE 2 of 2 (second 20-min run) — his three-confirmation setup, built exactly (UQQnN6cry8A)

He builds this one on screen from a blank chart and reads out every single setting,
which makes it the most precisely specified strategy in the catalogue.

### THE SETTINGS, verbatim

> "we're going to click RSI or type in RSI... we're going to go to settings... **this
> is where it's important the upper band needs to be 75 and the lower band needs to
> be 25** okay **inputs are going to stay 14**"

> "anytime the **RSI breaks below the 25 Zone we're looking for buys** and anytime it
> **breaks above the 75 Zone we're looking for sells** okay... **not always accurate
> do not use it by itself**"

> "we're going to type in Bowling your bands okay these settings right here... we're
> going to **change the inputs to 34**"

Not 70/30. Not Bollinger 20. **75/25 and 34.**

### THE THREE CONFIRMATIONS, in his order

> 1. "**first thing** that we want to do... is to kind of **dictate which way the
>    market is moving**... we're not looking for the actual trend line in a way like
>    this... we just want to see which way is the market moving... this market on
>    gbpnzd is going down this is a downtrend what does that mean **we are only
>    looking for sells and nothing else**"

> 2. "our **second thing** we're going to look for is **support or resistance**...
>    we're looking for sells we're on a down position we're looking for resistance...
>    we're going to take our **box** right here and just kind of draw this out"

> 3. "**third confirmation** check out our Bower bands they have been **broken out of**
>    indicating a very very **weak weak weak Trend that's going to come to an end**"

And the tell he watches at the level:
> "we can see these **Wicks right here are starting to get bigger and bigger** and
> they're starting to kind of reject as we're coming to this resistance"

### STOP

> "me personally I want my **stop loss Above This Little Resistance** okay **where
> these Wicks have gone** so I'll have my stop loss above that"

### TARGETS — and the sequence that makes his breakeven move safe

> "I'll probably have my **take profit maybe one** would be like right here just in
> case it stops right here at this little resistance... my **takeprofit two** will
> then be down in this area"

> "**take profit one right there did get smashed** okay we would have our **stops at
> break even** and then boom **takeprofit two would have got smashed out**"

The order is: bank the first target, THEN move the stop to entry, then let the rest
run. Earlier in this project I tested a breakeven move and it cost money -- but I
was moving the stop BEFORE anything was banked. His sequence banks first. Built to
his order.

### Not built, on purpose

He shows a buy/sell robot indicator on screen and says "**I usually don't vouch for
stuff like this**". Left out.

### Numbers, 15m, 10 months, 5% risk

| market | his exact settings | RSI band relaxed |
|--------|-------------------|------------------|
| US30 | 0.92x on 0.01/day | 0.58x on 2.04/day |
| XAUUSD | 1.10x on 0.02/day | 0.59x on 0.29/day |
| GBPUSD | 1.03x on 0.01/day | 0.61x on 1.78/day |

Registered `mamba_rsi` at his exact settings and `mamba_rsi_loose` with the band
relaxed. RSI 75 on a 15-minute chart is reached rarely, which is why his exact
version takes 2-4 trades in ten months.

### Also found scanning all 88 transcripts for mechanics not yet in the code

**Fibonacci is mentioned in 36 separate places** -- by far his most-used tool that
is still unbuilt. Next cycle's first job.

> "we also were in that little bit of a **fibonacci zone** while kind of making this
> little bit of a support here as well i knew that we were going to go bullish"
> "we even might have another **Fibonacci test** from here to here... just just being
> confluence"

Others named but rarer: fair value gaps and liquidity (9), double tops (7),
engulfing candles (2), MACD divergence (1).

---

## Leo's correction: he trades EVERY DAY, on ALL his markets

Leo pointed out the obvious thing I had not done: "mamba trades everyday like he
always trades gold and nas and etc". Correct. A single setup on a single market
gave 0.52 trades a day and **71 completely idle days out of 220**. He is never idle
for 71 days.

> "i'm actually going to be full time trading just **nasdaq us 30 gbp usd** and all
> of my **cryptos**"
> "With New York session, **6:30 every morning is always the time to trade**"
> "**Tomorrow, I'll do it again.** I'll make more"

Built `mamba_all.py` -- his three setups tried in turn on whatever market it is
pointed at -- and ran it across his watchlist: gold, US30, NAS100, GBPUSD.

| risk | growth | trades/day | days it traded | win% | drop |
|------|--------|-----------|----------------|------|------|
| 2% | 0.35x | **2.55** | **211 of 222** | 37.3% | 68% |
| 3% | 0.19x | 2.55 | 209 of 222 | 37.8% | 84% |
| 5% | 0.20x | 1.87 | 149 of 222 | 39.5% | 84% |

**His frequency and his coverage are now reproduced exactly**: two to three trades
a day, active on 95% of trading days, spread across the markets he actually names.
The idle-days problem is gone -- 11 quiet days instead of 71.

Money at 2% risk: 0.35x over ten months. Registered as `mamba_all`.

---

## BACKLOG ITEM 1 — FIBONACCI, built. His "gold zone".

His most-used tool: 14 videos, 36 statements. And he is far more restrictive with
it than the toolkit allows -- out of every Fibonacci level he trades **two**.

### THE LEVELS

> "we wait for it to come back and reject our **gold zone which is the zero five
> zone or the 0.61 our 0.618 zone**"
> "the Fibonacci is just a **zero point five or six one eight** zone **that's the
> only zones I want to see get rejected**"
> "price does not break through this **gold Zone that 0.5 68618 rejection Zone**
> then I'm fine"
> "look at this beautiful **50 and a 6-1-8 rejection** beautiful rejection right here"

**0.5 to 0.618. He calls it the gold zone.** One mention of an alternative:
> "it could be a **382 or a 50** rejection"

### HOW HE DRAWS IT

> "take my Fibonacci I'm gonna **draw from this low to this high**"
> "I'm **not gonna draw my Fibonacci from this wick** because this candlestick to me
> is **not really set as that push**"
> "I'm gonna go and **draw my Fibonacci from this wick right here to the top**"
> "you take your fibonacci **from this little red candlestick**"

Across one impulse push, from the wick that started it to the extreme that ended it.
His refusal of a wick that is "not really set as that push" is built as a minimum
move size -- a push has to be big relative to the noise or it is not a push.

### THE ENTRY

> "what am I gonna do here I'm gonna **wait for a Fibonacci setup to occur** now that
> I see this **huge rejection to the downside**"
> "very simple **we wait for it to come back and reject our gold zone**"
> "you go on the **15 and get your Fibonacci entry**"

### AND HE STACKS IT — five confirmations named in one breath

> "that's two confirmations if not like six by because we already know the **h4 shown
> bullish** the **MA is our crossing over on the h4** the [MAs] have **crossed over on
> the 15** we've got our **fibonacci zone** on this choppy setup and now we see a
> **support on a former resistance** this is a great buy"

> "instead of just looking for five minute 15 minute entries just randomly using your
> fibonacci **look at higher time frames** and see what's going on"

The moving-average crossover is built here as an option because he names it in the
same breath as the gold zone.

### Numbers, 15m, 10 months, 3% risk

US30 0.39x on 0.34/day, NAS100 0.82x on 0.47/day, GBPUSD 0.77x on 0.08/day, gold
took no trades at all -- the minimum push size is likely too large for gold's range
and wants a per-market value.

---

## BACKLOG ITEMS 2-5 — the four patterns he names, all built

`tradebot/strategy/mamba_patterns.py`. Every one from his own words.

### DOUBLE TOP / BOTTOM — he reads them as letters

> "whenever the market makes an **m** uh it's pretty obvious what's going to happen
> right we have a **double top resistance** while the beginning of the letter m has
> been created"
> "on the h4 you want to find either a major support or major resistance that price
> has showed it's going to respect for example right what do we have here beautiful
> beautiful **double bottom strong support** made"

And he feeds it straight into the gold zone:
> "I know a lot of you guys are asking **you see a double top** like why is this your
> entry check this out you're gonna take... my **Fibonacci** I'm gonna draw from this
> low to this high... look at this beautiful **50 and a 6-1-8 rejection**"

### ENGULFING CANDLE — his test is SIZE, not the textbook shape

> "we had a beautiful beautiful **bearish engulfing candle**... overall this is pretty
> much **engulfing every candle from the last it's been a cool minute since it's been
> that big**"
> "why do I still believe this is a bullish trade because **look at the size of this
> candle** this is a very **large engulfing bullish candle**"
> "we saw this candle here closed not only a **ginormous bullish engulfing candle** but
> it **closed above the tops of those rejections**"

Three conditions because he names three: swallows the previous bar, large against the
recent average, and closes beyond the level being tested.

### FAIR VALUE GAP

> "Right here, we're going to have a **fair value gap**."
> "We have that other **fair value gap now supporting price**."
> "maybe go to break even once we get down into this **order block** here, just in case
> price does react off of it"

### LIQUIDITY SWEEP

> "I'm liking this **liquidity that we're building up** up here."
> "our entry came from this **4-hour liquidity sweep**"
> "the next point could be here as an **area of liquidity**"

Built as the failure rather than the break: price pushes past an old extreme and
closes straight back inside it.

### MACD DIVERGENCE

> "**lower lows higher high on our macd** all that means is that price is **bound to
> reverse**"

### VERIFIED FIRING — the check that matters given this project's history

US30 15m, 3,960 sample points:

| pattern | fires |
|---------|-------|
| fair value gap | 66.2% of bars |
| double top/bottom | 26.3% |
| MACD divergence | 25.8% |
| liquidity sweep | 15.3% |
| engulfing | 3.8% |

None is a silent no-op. The double-top detector needed two fixes to get there: at my
first tolerance it fired on **81.7%** of bars, and tightening the tolerance alone only
took it to 77.7%. The actual bug was searching every historical pair in the window --
a double top he would point at is one whose **second peak is what price is doing right
now**, so it now requires the pattern to have formed within the last few bars. A
detector that is true 82% of the time is the same as no detector, which is the fifth
time this project has produced a rule that silently did nothing.

---

## Leo's second correction: THE PATTERNS DECIDE BUY OR SELL

He said it plainly: "he said that determines if u buy or sell thats lit what he
does those are important". Correct, and I had them as optional filters bolted onto
a direction worked out some other way. That is backwards. Every pattern he names
points a way, and the pattern IS his reason:

> "whenever the market makes an **m** uh it's pretty obvious what's going to happen
> right we have a **double top resistance**" -- M means sell.

> "what i saw was a very **bearish candle that just engulfed all this** while our
> **moving averages are above everything** i'm pretty sure the moving averages here
> are just gonna **pull our trade to the downside**" -- bearish engulfing means sell.

> "our **entry came from this 4-hour liquidity sweep**" -- highs swept and failed
> means sell.

> "**lower lows higher high on our macd** all that means is that price is **bound to
> reverse**" -- divergence ends the move.

> "We have that other **fair value gap now supporting price**" -- a gap under price
> is a reason to buy.

Built `mamba_signals.py`: every pattern votes, the trade goes the way they agree,
and "two confirmations if not like six" is the vote threshold.

### Wired in, and measured — 3% risk

| build | growth | trades/day | win% | drop |
|-------|--------|-----------|------|------|
| fib alone, US30 15m | 0.40x | 0.34 | 13.2% | 62% |
| **fib + his double top** | **1.05x** | 0.15 | 26.5% | 16% |
| fib + macd divergence | 0.91x | 0.08 | 22.2% | 14% |
| NY plain, US30 5m | 1.12x | 2.42 | 42.6% | 35% |
| NY + engulfing trigger | 0.89x | 0.32 | 34.8% | 16% |
| NY + liquidity sweep | 1.12x | 2.42 | 42.6% | 35% |
| **NY + fair value gap stop** | **1.18x** | **2.46** | 40.2% | 33% |
| NY + all three | 0.76x | 0.40 | 27.6% | 28% |
| patterns vote, 2 agreeing, US30 5m | 0.80x | 2.64 | **47.9%** | 36% |
| patterns vote, 3 agreeing | 0.73x | 1.59 | 46.6% | 37% |
| patterns vote, 4 agreeing | 0.91x | 0.23 | 41.2% | 11% |

Two things stand out. **His double top lifts the fib from 0.40x to 1.05x** -- the
pairing he describes is the one that matters. And **the fair value gap stop gives the
best result measured this session at 1.18x on 2.46 trades a day**, which is his
frequency with money above break-even. Letting the patterns vote gives the highest
win rate seen anywhere in this project at 47.9%.

---

## BACKLOG ITEM 6 — his crypto markets, and THE BUILD

Fetched 10 months of 15-minute history for the crypto on his screen: BTC, ETH, LTC,
XRP (28,752 bars each, Oct 2025 - Jul 2026). Then ran his patterns across his entire
watchlist at once.

### Full watchlist: gold, US30, NAS100, GBPUSD, BTC, ETH, LTC, XRP

| build | growth | trades/day | days traded | win% | drop |
|-------|--------|-----------|-------------|------|------|
| patterns vote, NY session, 2%, cap 3 | **1.21x** | **2.98** | **302 of 304** | **47.1%** | **27%** |
| patterns vote, NY session, 2%, cap 2 | 1.11x | 1.99 | 302 of 304 | 47.2% | 24% |
| patterns vote, round the clock, 2% | 0.52x | 4.11 | 304 of 304 | 42.1% | 48% |
| patterns vote, round the clock, 3% | 0.37x | 4.11 | 304 of 304 | 42.2% | 64% |
| all his setups, 2% | 0.27x | 3.98 | 298 of 304 | 37.2% | 76% |

**This is everything asked for, together, for the first time:** his patterns deciding
the trade, his whole watchlist, 2.98 trades a day, active on 99% of days, 47% winners,
above break-even, and the smallest drawdown of anything that makes money.

### The surprise: his session discipline holds on markets that never close

Crypto trades 24/7, so there was no obvious reason to keep his New York window on it.
Removing it takes **1.21x down to 0.52x and doubles the drawdown to 48%**. His "I don't
like to trade much past 10:00 a.m. -- I don't want to sit here and freaking trade all
day and trade into the evening" turns out to matter on BTC as much as on the Dow.

Registered as `mamba_signals`, with a two-a-day variant and a round-the-clock variant
for reference.

Note on the trade rate: an earlier printout said 4.08 a day because it divided by
weekdays only while crypto trades weekends. Per calendar day the real figure is 2.98,
which is exactly the cap, meaning the cap binds every single day.

---

## BACKLOG ITEM 7 — his 1-minute chart

> "It's very important that you use a **5-minute or 1-minute chart** simply because we
> are **super scalping**."
> "with these **one minute trades you got to get in you got to get up quick**... they're
> **reversing and they reverse fast**"

Fetched 45 days of 1-minute history for BTC, ETH and LTC (about 64,800 bars each);
US30 1m was already on disk. His patterns on 1-minute bars at 2% risk:

| market | out in 10 min | out in 35 min |
|--------|---------------|---------------|
| BTC | 0.93x on 2.84/day | **1.04x on 2.75/day, 45.5% win** |
| ETH | 0.79x on 2.80/day | 0.97x on 2.61/day |
| LTC | 0.92x on 2.68/day | 0.81x on 2.68/day |
| US30 | 0.82x on 1.85/day | 0.78x on 1.87/day |

## BACKLOG ITEM 8 — the daily, built right this time

The first attempt was switched off because I had guessed what the daily was for. He
says outright what it is for, and it is ONE thing:

> "how i'm trading it is **first off i need to determine are we going up are we going
> down** are we in a bullish trend or a bearish trend are you making bullish moves or
> bearish moves right and **that's going to be from the daily and the four hour**"

**Direction. Not levels, not zones.** My earlier stand-in measured where price sat
inside a daily range, which is why it was useless.

And he ranks them, which settles which one leads:

> "we're gonna **start on the h4 always h4** you can **use the daily as well i like the
> h4**"

So the H4 decides and the daily can only disagree. Also worth recording, on how far
back to look:

> "I'd go on the weekly and then slowly go down to the 5minut chart and it's like,
> holy [bleep] **do I really need to see every single thing that's happened for the last
> 20 years?**"

And the stack he names for levels:
> "remember guys, **H4 support resistance daily and weekly**"
> "Looking at our **weekly**, we actually may be coming to a support as well, which is
> **good confluence**"

### Numbers, 10 months, 2% risk, all eight markets

| build | growth | trades/day | win% | drop |
|-------|--------|-----------|------|------|
| no higher-timeframe gate | 1.21x | 2.98 | 47.1% | 27% |
| H4 gates direction | 0.76x | 2.98 | 44.9% | 36% |
| H4 over 8 hours | 0.67x | 2.98 | 43.8% | 51% |
| daily gates direction | 0.65x | 2.85 | 44.5% | 46% |
| H4 and daily must agree | 0.62x | 2.70 | 44.0% | 55% |
| as equal votes instead | 0.89x | 2.98 | 44.5% | 43% |

Both registered: `mamba_signals_h4` and `mamba_signals_h4_daily` are his stated order,
`mamba_signals` is the ungated version. His order also beats treating them as equal
votes (0.76x against 0.89x is the wrong way round, but the H4-only gate at 0.76x beats
the both-gates 0.62x, so his preference for the H4 does hold).

**THE BACKLOG IS COMPLETE.** All eight items built: Fibonacci, fair value gaps,
liquidity, double tops, engulfing candles, MACD divergence, his crypto markets, the
1-minute chart, and the daily.

---

## PIXEL READ — "MAMBAFX Scalping LIVE Making $30,000 Trading" (1v4ssSHMEdc)

Backlog complete, so this is new material read off the screen rather than the audio.
A live trade with his order buttons armed. What is actually measurable:

### HIS RISK-REWARD, MEASURED OFF THE DRAWN BOXES

He has TWO position tools on the chart at once, one long and one short, because he
has not committed yet -- the same "price will either respect this or hit that, one
or the other" logic as the channel video.

* **Long setup:** red risk box 46,790 -> 46,811 (**21 points**), green reward box
  46,811 -> 46,960 (**149 points**). That is **1:7.1**.
* **Short setup:** red risk 46,790 -> 46,811 (**21 points**), green reward
  46,620 -> 46,790 (**170 points**). That is **1:8.1**.

**Pixel confirmation of "we have a fat one to seven, one to 10 risk to reward."** Not
1:3 on this one. The 1:3 videos are his indices day trade; the 1:7-1:8 boxes are what
he actually draws when flipping.

### PIXEL CONFIRMATION OF HIS START TIME

Chart clock reads **06:35 on Tue 07 Oct '25**, with the entry forming right there.
That is his "6:20, 6:30 a.m." said in a different video, now confirmed on screen.

### TIMEFRAME

**5m** highlighted in the toolbar. 1m / 5m / 15m / 30m / 1h / 4h / D available.

### A FIBONACCI TOOL IS ON THE CHART

Levels are labelled with prices beside them, drawn across the push into the entry --
so the gold zone is not just something he says, it is loaded while he trades.

### AN ASCENDING TRENDLINE, and price sitting on it

Drawn from the 04:30 low up through the subsequent lows, with price at it when the
entry forms. This is the "I drew my trend line... we're getting in as soon as this
trend line or the support zone breaks" mechanic, visible in the wild.

### HIS WATCHLIST IS WIDER THAN WHAT IS BUILT

Titled "Scalping BIG…" and reads: **XAUU (gold), GBPU (GBPUSD), UK10 (UK100),
FRA4 (FRA40), BTCU, ETHU, XRPU, NAS1 (NAS100), US30, NQ1! (Nasdaq futures),
YM1! (Dow futures)**.

Built so far: gold, US30, NAS100, GBPUSD, BTC, ETH, LTC, XRP. **Missing from his
screen: UK100, FRA40, and the NQ/YM futures contracts.** The futures are the same
underlying as NAS100 and US30 so they add nothing, but the two European indices are
markets he watches and the bot does not.

### UK100 added, and a live-money bug found while fetching it

UK100 is on his screen and tradable on the account, so it went in. FRA40 is on his
screen but the broker does not offer it -- recorded rather than substituted, since
swapping in a different index would not be copying him.

| watchlist | growth | trades/day | win% | drop |
|-----------|--------|-----------|------|------|
| 8 markets | 1.21x | 2.98 | 47.1% | 27% |
| 9 markets, + UK100 | 0.89x | 2.96 | 45.3% | 31% |

**Fetching it exposed a bug that would have cost real money.** TradeLocker answers an
over-wide time range with an EMPTY bar list rather than a short one. On UK100, asking
for 5,000 bars of 15m returned 5,000; asking for 20,000 returned **zero**, because
20,000 bars of 15m requests a 626-day window and the endpoint declines it.

An empty candle list is indistinguishable from an instrument with no history. A live
strategy pointed at any market thinner than US30 would have received nothing, taken no
trades, and looked exactly like a strategy with no signal -- the same failure shape as
every other silent bug in this project, except this one happens with money at stake.

Fixed: the request now halves the window and retries rather than accepting the silence,
warns when the server had fewer bars than asked for, and raises if there is genuinely
no history at any width. UK100 now returns 19,618 bars where it returned 0. Three
regression tests cover the narrowing, the short-history case, and the genuinely-empty
case.

---

## CYCLE 6 — two mechanics found by scanning all 144 transcripts against the notes

### HE DOES NOT WAIT FOR THE CANDLE TO CLOSE

> "**As soon as it breaks, we're not waiting for candle to close**, we're not waiting
> for no [bleep] other confirmation."
> "i **don't take trades based on closed candles i take trades based on moving
> candles**"

Every strategy in this project except `MambaBreakout` tests `bar.close` against the
level, which means waiting for the bar to finish -- the opposite of what he says.
Added `wait_for_close` to `MambaSignals`. When off, the pattern only has to have been
reached during the bar; the fill still happens at the bar's close, which for a
breakout is a WORSE price than the level, so it cannot flatter the result.

### HE TRADES THREE SESSIONS, NOT ONE

> "16 targets hit, one stop loss last week, uh **6 in one for London session** and then
> for **Asia session, 10 in one**."
> "yesterday during **Asia session**, I took that trade that I showed you guys"
> "All righty, boys, you know that yesterday **during Asia session** I tried taking two
> trades."

Asia and London as well as New York, and he counts them separately. Built as a
`sessions` tuple replacing the single session.

| sessions traded | growth | trades/day | win% | drop |
|-----------------|--------|-----------|------|------|
| New York only | 1.21x | 2.98 | 47.1% | 27% |
| London + New York | 0.62x | 2.98 | 41.3% | 42% |
| Asia + London + New York | 0.52x | 2.98 | 42.0% | 48% |
| all three, 4 a day | 0.44x | 3.97 | 40.8% | 57% |
| all three, 6 a day | 0.22x | 5.95 | 42.1% | 79% |

### Also recorded, not built

He says in one video "Zero indicators, just pure price action, trends, market
structure" while using RSI, Bollinger bands and moving averages in others. Both are
his, from different videos, so both stay available rather than one overriding the other.

And on brokers, repeatedly: "there's **no spread** like it's pretty much zero", "when I
enter that trade, I am **instantly in profit, if not at break even, because there's no
spread at all**". Every backtest in this project charges spread, so the numbers here are
pessimistic against the conditions he describes trading in.

---

## HOW HE AVOIDS LOSSES — Leo's question, and what the loss side actually shows

Leo: "the trade doesnt go his way with stop loss its like he didnt even lose money".
Real, and he describes several mechanics for it.

### BREAKEVEN AT 1:2 — his number, and mine was wrong

> "let's say we got to a **1 to two stops can go to break even** and boom the rest is
> history"
> "We're **taking some profit** and we are going to put uh **stops to break even, near
> break even**, and pretty much just take profits along the way."
> "after you **close partial profits and move stops to break-even**"
> "price is already up 500 Pips **put your stops to break even** and the rest is going
> to always be [profit]"

**Two R, not one.** Every earlier breakeven test in this project used 1R, which is why
it kept cutting winners in half.

Note "**near** break even" -- a shade the right side of entry, so a scratch is
fractionally green. Built as `breakeven_pad`.

### HE LEAVES WHEN THE REASON DIES — the actual no-loss mechanic

> "as price came down on this candle **I ended up closing around this area um just
> because I wasn't sure if price was going to fully reverse here**"
> "good for us **trend got broke** you know the **candle is closed below** it's just
> **it's not going to come back**... it's not looking good"

He does not sit and wait to be proved wrong by the stop. When the reason stops being
true he leaves, and the trade costs a fraction of a stop instead of all of it. Built as
`exit_on_reason_gone`: if the patterns turn against the open trade, close it.

### STOPS NEVER WIDEN

Searched all 144 transcripts for any mention of moving a stop further away: **zero
statements**. So the rule is one-directional and now enforced -- a stop only ever moves
toward profit.

### RE-ENTRY after getting out

> "I decided **I got out too early I want to re-enter this trade**"
> "I'm going to go ahead and **re-enter longs** right now"
> "I would **re-enter for a buy**" (after price pushes back above the resistance)

### THE LOSS PROFILE, measured — 10 months, 8 markets, 2% risk

| build | growth | full stops | scratched | win% |
|-------|--------|-----------|-----------|------|
| registered | 1.21x | **6.7%** | 46.1% | 47.1% |
| breakeven at 1R | 1.21x | 6.8% | 46.1% | 47.0% |
| breakeven at 2R (his) | 1.21x | 6.7% | 46.1% | 47.1% |
| + exit when reason dies | **1.22x** | **6.0%** | 47.7% | 46.4% |
| everything | 1.22x | **5.9%** | 47.6% | 46.4% |

**Only 6% of trades take a full stop.** That is the profile Leo is describing, and it
is already there.

### But the honest reason why, which is not the breakeven rule

Counting how trades actually end:

| hold | closed by the clock | by the stop | by the target |
|------|--------------------|-------------|---------------|
| 35 min (registered) | **83%** | 15% | 2% |
| 240 min | 54% | 38% | 8% |
| no cap | 0% | 73% | 27% |

**His 35-minute clock is what prevents the losses, not the breakeven move.** At 35
minutes a trade almost never reaches 2R, so the breakeven rule has nothing to act on --
it is built, correct, and inert at this hold length. Caught before claiming otherwise;
that would have been the eighth rule in this project that looked like it worked while
doing nothing.

The reason-gone exit is the one addition that measurably improves the loss side: full
stops 6.7% -> 6.0%.

---

## "SO HE BARELY LOSES MONEY" — mastered, and the answer is not the stop

Leo: "remember the specific way he does a stoploss if he loses the trade so he barely
loses money so it looks like he barely traded at all".

### HIS STOP SIZES, every one he states

> "**22 pips stop-loss** with a 50 80 take profit"
> "**16 pips stop-loss** 51 pip take profit... if you get stopped out on a setup like
> this on a 15 minute **you're gonna lose very little**"
> "**13 pip stop loss**"
> "i have a **10 pip stop loss 50 pip take profit** and uh we've just been smashing it"
> "we have a **44 45 pip stop**"
> "let's do a **30-tick stop loss, which should be just underneath that low**, and then
> let's do a 60-tick TP"
> "I'm only gonna have a **25 Point slash 250 pip stop loss**" (for a 1000-pip target)

### AND HE NAMES TIGHTNESS AS THE KEY

> "here's the key with the strategy, **super, super tight stop losses**"
> "I'm having a **super super super tight stop loss**"
> "I want to get in **very fast, tight stop loss, and I want that one to five**"
> "try this strategy, **super tight stop losses, go for those one to fives**"

### HIS LOSS-AGAINST-WIN MATH

> "I know that if this hits a loss I'll probably **lose 50 bucks** if this hits a win
> I'm gonna **make 500**"
> "I had you know **10 pip loss 15 pip loss** uh 10 pips and 20 pips profit"

### A STOP LOCATION NOT BUILT UNTIL NOW

> "have our **stops just below our moving average** because price pretty much respects
> it as a support"
> "**stops are gonna be just below that moving average**"

### THE ACTUAL MECHANIC, and it took measuring to see

A tighter stop does NOT make the cash loss smaller when the position is sized to a
risk percentage. Sizing to 2% means 2% is lost whether the stop is 10 pips or 100 --
the tighter stop just buys more lots:

| stop | lots bought | loss if stopped |
|------|-------------|-----------------|
| 10 pips | 0.030 | 2.00% |
| 16 pips | 0.019 | 2.00% |
| 100 pips | 0.003 | 2.00% |

**His small losses come from a small FIXED lot meeting a tight stop.** That is what
"if you're using a 0.01 that would have been a dollar sixty loss for a five dollar and
10 cent gain" describes -- 0.01 lots, 16 pips, $1.60. At a fixed 0.01 lot the stop
width IS the loss: 10 pips costs 0.67% of $150, 16 pips 1.07%, 44 pips 2.93%.

Built `lots` on `Enter` so a strategy can size his way instead of by percentage.

### But measured on Leo's actual account size, his sizing is the dangerous one

| sizing | growth | worst single loss | avg loss | drop |
|--------|--------|-------------------|----------|------|
| risk 2% (registered) | 1.21x | **2.04%** | **0.70%** | 27% |
| fixed 0.01 lots | 0.18x | **54.57%** | 1.80% | 88% |
| fixed 0.01 + tight stop 0.20% | 0.52x | 8.02% | 0.81% | 57% |
| fixed 0.02 lots | 0.11x | 37.12% | 3.52% | 89% |

A fixed 0.01 lot is only small on FOREX. On gold 0.01 lots is an ounce, and on BTC it
is about $1,200 of notional -- so one bad candle is a third of a $150 account. His
"$1.60 loss" was a forex pair with a 16-pip stop, not gold or crypto.

**The percentage sizing already delivers what Leo is asking for**: worst single loss
2.04%, average loss 0.70%, and full stops on only 6% of trades. That is a bot whose
losses barely register. It gets there by sizing down rather than by tightening the
stop, which is the same destination by the arithmetic his own numbers imply.

---

## HIM. Every strategy he has, in one bot, nothing of mine overriding him

Leo: "u dont change anything, your mamba fx yourself... use every single strategy he
has" and "also do his risk as well, no difference, everything the same, only speed".

Fair. Two things I had been doing were me overruling him:

1. **His direction rule was switched OFF.** He is explicit: "first off i need to
   determine are we going up are we going down... and that's going to be from the daily
   and the four hour", and "we're gonna start on the h4 always h4". I turned it off
   because it took 1.21x to 0.76x. That is ten months of replayed history overruling
   ten years of his live screens. **Back on, and checked first, as he states it.**
2. **His risk was replaced with mine.** He says "3 to 5 percent max" carefully, and
   "risking 10%", "risking 15%", "risk 25% of your account, which is kind of what
   you're going to have to do" to flip a small account. I ran 2%. **Now run at his.**

`mamba_complete.py` arms every setup he teaches, tried in the order of how decisively
he describes taking it:

1. **New York session break** — with his trendline and his volume rule both on
2. **Fibonacci gold zone** — paired with the double top, as he pairs them
3. **Break and retest** — with his 50 moving average and his trail
4. **Three-confirmation setup** — RSI 75/25, Bollinger 34, his exact settings
5. **Channel fade** — with his two-timeframe rule
6. **Pattern confluence** — with his H4-and-daily gate ON and FIRST

Plus his management throughout: breakeven at 1:2, half off, doubling up on a winner,
out in 35 minutes, three trades a day, two losses ends the day, and leaving when the
reason dies.

Nothing in the file is tuned to improve a number. Where he gives a value it is his
value; where he gives none it comes from what he draws on screen.

---

# PARAMETER AUDIT — every number in the code, his or mine

Leo's instruction: "for EVERY number in every file, answer: did he say this, or did I
pick it?" Here it is. 117 parameters across 9 files.

## HIS — quoted, verbatim

| parameter | value | his words |
|-----------|-------|-----------|
| `rsi_period` | 14 | "inputs are going to stay 14" |
| `rsi_upper` | 75 | "the upper band needs to be 75" |
| `rsi_lower` | 25 | "the lower band needs to be 25" |
| `boll_period` | 34 | "we're going to change the inputs to 34" |
| `fib_near` | 0.5 | "the zero five zone" |
| `fib_far` | 0.618 | "the 0.61 our 0.618 zone" |
| `ma_slow` | **50** | "You're going to make it a **50 simple** moving average" |
| `ma_fast` | **8** | "make this a **eight**... a eight blue simple moving average" |
| `max_hold_minutes` | 35 | "30 minutes, 35 minutes at the most" |
| `max_trades_per_day` | 3 | "two, three when I like it" |
| `max_losses_per_day` | 2 | "If the second one doesn't work out, we are done for the day" |
| `window_minutes` | 210 | "6:20, 6:30 a.m." to "I don't like to trade much past 10:00 a.m." |
| `session` | newyork | "you only trade during New York session" |
| `reward` | 3.0 | "we can go for a nice little one to three" |
| `reward` (flip) | 7.0 | "a fat one to seven, one to 10 risk to reward" |
| `breakeven_at` | 2.0 | "we got to a 1 to two stops can go to break even" |
| `min_touches` | 2 | "a couple touches... it's not perfect" |
| `fixed_lots` | 0.01 | "if you're using a 0.01 that would have been a dollar sixty loss" |
| `zone_pct` | 0.0004 | pixel-measured off his drawn bands: 15-20 points on 49,400 |
| `wait_for_close` | False | "we're not waiting for candle to close" |

## MINE — he never states these

| parameter | value | verdict |
|-----------|-------|---------|
| `min_votes` | 2 | **mine.** He says "confluence" and "two confirmations if not like six", never a count. |
| `push_bars` | 60 | mine |
| `min_push_pct` | 0.004 | mine |
| `level_bars` / `level_lookback` | 60 / 200 | mine |
| `trend_bars` | 48, 60 | mine |
| `stop_bars` | 24 | mine |
| `retest_bars` | 24 | mine |
| `stop_beyond_pct` | 0.0008 | mine |
| `stop_zone_frac` | 0.5 | mine |
| `target1` / `target2` | 1.5 / 4.0 | mine. He says "take profit one / take profit two" with no numbers. |
| `boll_stdevs` | 2.0 | his by omission -- he changes the period and leaves this alone |
| `edge_pct`, `stop_pct`, `target_pct`, `min_width_pct` | | mine, all in mamba_channel |
| `trail_after` | 6.0 | mine. He says he trails, never how far. |

## CORRECTED THIS CYCLE — three numbers that were wrong, not just unsourced

**`ma_fast` and `ma_slow` were EMA 9 and 21. Both wrong, and the type was wrong too.**
He builds them on a blank chart and reads out every setting:

> "we need to set up two things. Okay, that's just **two simple moving averages**"
> "You're going to make it a **50 simple moving average**. Go ahead and make it red."
> "Then you're going to take another moving average and you're going to go ahead and
> make this a **eight**. Okay, I make it blue... for me, it's a **eight blue simple
> moving average**."
> "You now have a **eight and a 50** moving average on your screen. **That's all we're
> going to be using.**"
> "**simple ones are a lot better** by the way"

He names the 50 in **22 separate places** across the videos. He names 9 or 21 in
**none**. Changed to SMA 8 and SMA 50 in both files that used them.

**His entry trigger is the CROSSOVER, which was not built at all:**
> "we're going to be looking for **crossovers on the 5 minute time frame**"
> "We are now going to go to our **5m** and we're going to go ahead and see if we can
> get a **moving average crossover**"

A crossover is an event -- the 8 crossing the 50 on this bar -- not the state of being
above it. Built as its own vote.

## NEW LEVEL SHAPE — his "buildup zone", and every detector here was looking for the wrong thing

> "support and resistance is **not always going to be what you think it is**. Okay,
> it's not always going to look like right or this... all it really is, it's just a
> **buildup**. When you have a **buildup in a zone on a H4**, a lot of times it's going
> to get respected."
> "That's support because it's rejecting that zone multiple times. It doesn't look like
> one of those **solid supports**... It's just a **buildup in the moment off a bunch of
> candles. It's a buildup zone. It's support.**"

Every level detector in this project hunts swing highs and lows -- single extremes with
bars either side. That finds exactly the "solid supports" he says a level is NOT always
shaped like. A buildup is the opposite: a stack of ordinary candles congesting in a
narrow band. Built as `buildup_zone`, and wired as a location that votes only when
price returns to it and is refused, because that is the "respected" part.

## HIS TIMEFRAME STACK, stated in full for the first time

> "we're going to be based upon **higher time frame support resistances**... and then
> **smaller time frame entries**"
> "right here, **H4**, we have a support buildup"
> "Looking at our **daily**, nothing's telling us that we're selling... **we check our
> daily to make sure that that's the case**" -- so the daily is a VETO, which is how it
> is built
> "Looking at our **weekly**, we actually may be coming to a support as well, which is
> **good confluence**"
> "**don't use the hourly as much**"

H4 for the level, daily to veto, weekly as bonus confluence, 5m for the entry. The
weekly is still not built.

## EVERY SIGNAL VERIFIED FIRING — US30 15m, 788 samples

| signal | votes on |
|--------|----------|
| `ma` (side of the 50) | **100.0%** |
| `gap` (fair value gap) | 56.0% |
| `macd` divergence | 27.5% |
| `double` top/bottom | 25.3% |
| `sweep` (liquidity) | 15.6% |
| `buildup` zone | 12.6% |
| `engulfing` | 3.6% |
| `ma_cross` | 2.5% |

None is a silent no-op. But **`ma` voting on 100% of bars is a structural problem**:
price is always one side of the 50, so the MA always contributes a vote, which means a
threshold of two is really "the MA plus any one other thing". That is not the
"confluence" he describes, and the vote threshold was already flagged as mine rather
than his. Next cycle's job.

---

# HIS SUPER SCALPER — and the currency bug that hid in four places

Built `mamba_scalper.py` from the video where he sets up the whole thing on a blank
chart. Getting it to take a single trade uncovered a chain of five defects, four of
them the same root cause, and all four would have broken real trading on the one
pair he says he will trade "for the rest of my life".

## The strategy, entirely his

> "we need to set up two things. Okay, that's just **two simple moving averages**...
> You're going to make it a **50 simple** moving average... Then you're going to take
> another moving average and you're going to go ahead and make this a **eight**... You
> now have a **eight and a 50** moving average on your screen. **That's all we're going
> to be using.**"
> "**simple ones are a lot better** by the way, but I use the moving averages and I use
> **momentum**."
> "Anytime we see our **50 moving average cross over above**... It crossed above our 8
> moving average. **We're looking for sells.**"
> "if this 50 moving average can come below our 8 moving average, **cross below here,
> and then start to swoop to the upside**... we're going to be looking for **buys**."
> "what are our moving averages doing here, guys? And **this is very important to pay
> attention to**... They're coming down and they're **swooping**... Once they start to
> turn up, most the time this **momentum is going to pull all the way to the upside**...
> Because they're **curving**."
> "We just need to get some **bullish candles** just like that... This is a very **big
> engulfing candle**. So, we're going to go and take our buy position right here."
> "we're going to put our **stops below that previous support line**. Okay, **17 pips**.
> And we're going to target a **1:1 ratio**."
> "Remember, this is **only GJ**... **GJ is my [thing]** and uh it's pretty much what
> I'm going to be trading for the rest of my life."

## FIVE DEFECTS, found one at a time by asking why it took zero trades

**1. I collapsed his sequence into an instant.** Requiring the crossover, the swoop,
the buildup and the big candle all on the same bar gave 0 trades in 6,600 samples --
the funnel ran 3.03% for the cross, 0.68% with the swoop, 0.06% with the buildup,
0.00% with the candle. He does not do that: "that's all we're going to wait for,
right? **still would like to see it break above a bit before we take a buy entry**...
right here we start to break above." The cross ARMS the setup; the candle fires it
later. Fixed with an arming window.

**2. I checked the swoop at the wrong moment.** He says "cross below here, **and then**
start to swoop", so the swoop comes AFTER the cross. Checking it at the cross bar
cannot ever be true: at an upward cross the fast average is already rising, so "was
falling, now rising" is false by construction. 107 armed setups, 0 trades.

**3. My engulfing was stricter than his.** The textbook definition requires the bar to
swallow the previous bar's whole range. His emphasis is size -- "**look at the size of
this candle**", "it's been a cool minute since it's been that big". The textbook version
agreed with **none** of his 31 armed setups. Added `big_candle`, judged on size alone.

**4. THE CURRENCY BUG, IN FOUR PLACES.** GBPJPY settles in yen, and the codebase assumed
the quote currency is always the account currency:

   * **The sizer.** Told a yen is a dollar it valued every pip ~164x too highly, asked
     for 0.00008 lots against a 0.01 minimum, and refused every signal.
   * **The margin cap.** `notional_per_lot = price x contract_size` gave **21.6 million
     yen** for one lot, measured against dollars of free margin, capping the position at
     0.0003 lots.
   * **The P&L settlement.** `pnl_in_account` defaulted the rate to 1.0 and the paper
     broker never passed one, so a trade risking $4.46 was booked as a **$730** move
     against a $150 balance -- driving the account negative and printing a **267%
     drawdown** and **-6.04x** growth.
   * **And every refusal was silent.** `size_position` returned a bare `False` and the
     engine swallowed it, so 14 valid setups produced no trades and looked exactly like
     a strategy with no signal.

   Fixed: `quote_to_account_rate` now lives on the `Instrument`, the margin cap converts
   the notional, `pnl_in_account` defaults to the instrument's own rate rather than 1.0,
   and refused sizes carry a reason and are logged.

**5. My stop is still three times his width, and it silently disables his target.**
With all four currency bugs fixed the strategy trades: 16 trades, 31.2% winners,
average loss 0.33% of the account, worst drawdown 2%, growth 1.00x. But 1:1, 1:3 and
1:6 all return **identical** results, and the reason is that **every single trade closes
on the 35-minute clock** -- none reaches the target, none reaches the stop. A 0.25%
stop needs a 0.25% move inside 35 minutes and GBPJPY moves about 0.1%, so the clock
always wins first. His 17 pips is **0.087%**, which is reachable. The take-profit is
therefore the tenth rule in this project that was present and inert.

Next: place the stop AT his width rather than rejecting setups whose structure sits
wider, so his 1:1 has something to reach.

## Cycle 3 — his 1:1 made reachable, his re-entry built, an eleventh silent rule

### HIS TARGET NOW EXISTS

Clamping the stop to his 17-pip width instead of rejecting wider structure:

| target | growth | trades | how they closed |
|--------|--------|--------|-----------------|
| 1:1 | 0.97x | 21 | manual 9, **take profit 7**, stop 5 |
| 1:3 | 0.98x | 18 | manual 14, stop 4 |
| 1:6 | 0.98x | 18 | manual 14, stop 4 |

His 1:1 is hit **7 times out of 21**. Before the clamp all three targets returned
byte-identical results because nothing ever reached any of them.

### HIS RE-ENTRY — the best single addition measured all session

> "trade number three was really **trade number two part two** because it's still the
> same move we're still going up on the same day and I decided **I got out too early I
> want to re-enter this trade**"
> "I'm going to go ahead and **re-enter longs** right now"
> "now that we did break some highs, I think I **might just reenter** longs"
> "I would **re-enter for a buy**"

Every re-entry he narrates follows him CLOSING a trade, never being stopped out of one.
So it arms only after a manual exit -- the clock or the reason dying -- and not after a
stop.

**1.17x -> 1.36x on eight markets over ten months.** Registered as the default.

### SILENT RULE NUMBER ELEVEN — the weekly could not be seen

`weekly_bars=480` against a `lookback` of **400**. The rule asked for more bars than the
strategy is ever handed, so it returned zero on every bar of every market. Adding it
changed the result by exactly nothing, which is the signature.

Raised the lookback to 600. With the weekly genuinely voting: **1.36x -> 0.77x**, so it
hurts as an equal vote. He calls it "good confluence", not a requirement, which is the
same shape as the H4 and daily -- they belong as context, not as votes among equals.
Registered as a variant rather than a default.

Note the lookback is also what the live cycle requests from the broker, so it is the
real ceiling on what any rule here can look at. Worth checking against before adding a
long window.

---

## MEASURED: his tutorials carry the rules, his live streams do not

I told Leo the three live streams would be the best material there is and put them at
priority 0. **That was wrong, and measuring it says so plainly.** Counting how often
each video contains a buildable rule word -- stop loss, take profit, moving average,
fibonacci, a stated ratio, crossover, engulfing, buildup, timeframe -- per 1000 words:

| video | rules per 1k words |
|-------|--------------------|
| **tutorial, built on a blank chart** (Gav-iFiFDYs) | **34.5** |
| tutorial, futures (-VdyJZlCG1M) | 13.3 |
| tutorial, RSI + Bollinger (UQQnN6cry8A) | 12.7 |
| tutorial, $100 account (I_33XcywuIo) | 11.1 |
| live stream, Cave Talk (48 min) | 4.5 |
| live stream 1 (52 min) | 3.2 |
| live stream 2 (65 min) | **1.5** |

**The tutorials are 3x to 23x denser.** The live streams are largely chat with the
audience -- an hour of stream yields fewer buildable rules than four minutes of a
tutorial. And the single richest video in the catalogue is the one where he sets the
whole thing up on a blank chart and reads out every value, which is the one that gave
the SMA 8 and 50, the buildup zone, the swoop and the 1:1 target.

Tracker re-prioritised: anything that teaches the setup is now priority 0; the live
streams are demoted to 2.

### What the live stream did give — two clean confirmations

His entry rule, as compactly as he has ever put it:

> "**I'm going to take a sell if we're in a selling market and I see a support break.**"
> "**I'm going to take a buy if we flip to a buy market.**"

That is exactly what `MambaNY` does -- direction first, then the level giving way -- now
confirmed from a live session rather than a lesson.

And a risk-to-reward figure in passing:

> "you're still going to get that **130 pip move** and you only have to **risk, you know,
> 50 pips**"

1:2.6, consistent with the 1:3 he quotes elsewhere.

---

# ELEVEN-HOUR RUN — CYCLE 1

Eight subagents launched in parallel, one per priority-0 video: I_33XcywuIo, 9bPlk7zSJAI,
prtpGhzb22g, hGPg7_ZE1DM, I2I4EVPFoak, 4JKwM9CeLig, qM4A_6i21I0, qAvSFpKE4aE, dOv1jOSsYLU.
Each reads frames and audio and reports his words against all twenty dimensions.

While they work, doing the code side they are not: deleting my parameters and fixing the
H4/daily/weekly wiring, for which his words are already on record.

## Cycle 1 — first parameter of mine DELETED rather than tuned

`weekly_bars` is gone from `mamba_signals` and from the registry. Not defaulted off —
removed.

The reasoning, and it is the template for the rest of the deletions:

> "remember guys, H4 support resistance daily and weekly."
> "Looking at our weekly, we actually may be coming to a support as well, which is
> **good confluence**, right? That's a good good confluence."
> "If we look at the weekly, we're at a 10-year support."

Every single time he mentions the weekly, it makes him feel better about a trade he is
taking anyway. It never stops him and it never starts him. **A thing that cannot change
the decision is not a rule.** Wiring it as a vote among equals gave it power he never
gives it, and it outvoted the patterns that actually decide -- 1.36x down to 0.77x.

He looks at the weekly. The bot does not need to, because looking without acting is not
a behaviour a bot can have. So the parameter is deleted rather than kept at zero.

32 strategies still construct, 258 tests pass.

## Cycle 1 — video prtpGhzb22g, "6 Tips To Become a PRO SCALPER" (10:38)

Watched by subagent: full audio plus every frame. The video is entirely talking-head with
no chart walkthrough, but his live TradingView chart is visible on the monitor behind him
and was measurable.

### CONFIRMED, and it matches what is already built

His daily limits, tightened in his own words:

> "**my rule is i can only take three trades max in one day**"
> "**i mean i say three but i think two is better** but i will do three if i really have
> to but **really after two losses you should stop and wait till the next day**"

That is `max_trades_per_day=3` and `max_losses_per_day=2` exactly as built. And the
consequence:

> "**wait till the next day** let the markets refresh a little bit relax you know get
> your psychology back on track and then trade again"

### CORRECTED — re-entry was too loose

> "i'm not going to continue to re-enter **unless that trading strategy says it's still a
> good trade** right but don't over trade"

And the anti-pattern he names:
> "you can't just sit there and oh i took a 10 pip loss i'm going to re-enter oh i took
> another 20 pip [loss] i'm going to re-enter and go for a 300 pip game -- it's just not
> like that"

My re-entry only required the move to still point his way. His requires the setup to
still be valid. Fixed: a re-entry now needs the FULL vote threshold again, the same
confirmation a fresh entry needs.

### HIS GOLD NUMBERS — stop and target, stated

> "my stop losses when i trade gold they're like **15 pips 20 pips at the most**"
> "my take profits **my main targets are anywhere from 100 to 200 pips**"
> "very tight stop loss huge take profit **i'm going to trail my stop-loss all the way up**"

That is **5:1 to 13:1**, far above the 1:3 he quotes for indices. Note "main targets"
plural -- the only hint of multiple targets in this video, never explained.

**MEASURED off his chart:** a Long Position tool live on screen with a teal reward box of
241 pixels against a dark-red risk box of 40 pixels -- **approximately 6:1**, stable
across four sample columns. His spoken 15-20 pip stop against a 100-200 pip target
corroborates it.

### DIRECTION — three inputs, higher timeframes first

> "use your **daily and use your h4** to realize market structure which way is price going
> where are we trending"
> "whether it's **above your moving averages** or any of the other reasons"
> "look at **fundamentals what's happening with the news** positive news coming out for gold"
> "once you realize okay we're in a bullish market... now you're going to go to your five
> minute your 15 minute whatever you want to use **i use the five minute**"

### ENTRY — a 5-minute breakout

> "the way i trade is very simple i look for **breakouts on my five-minute chart**"

### A NEW EXIT, discretionary and not yet built

> "you're going to remember oh last time this happened i got stopped out **let me just get
> out early because this doesn't look good anymore** boom saved yourself from 10 pips
> which is a lot for scalper"

He leaves on pattern recognition -- having seen this shape fail before. That is judgement
rather than a rule, and it is the clearest example yet of the part of him that cannot be
copied from video.

### WHAT HE REFUSES — the bulk of this video

> "**you cannot go out there and take 30 trades in one night**... you don't want to mess
> with your psychology that much"
> "**don't ruin your psychology by taking 500 trades in a single night**"
> "**don't over trade** set yourself a limit"
> "don't sit there and just keep entering and doing crazy stuff just because you have
> tight stop losses -- trust me those **tight stop losses those little baby stops they add
> up fast** if you start to get crazy"
> "**don't go around looking for other strategies**... when you start to look at this
> strategy and this strategy you start to implement things from each strategy and **it
> just messes up the entire strategy**"
> "i don't care who tells you that -- **whoever your mentor is is lying to you**" (on
> never-lose claims)

### His own record, stated

> "the last month or so i've taken about 30 trades i lost four of those right so i think i
> went **26 wins four losses**... this is a really really really good month"
> "someone who you know been trading **five years and two of those years very
> unsuccessfully**"

### NOT IN THIS VIDEO

Sessions and clock times. Level definition and touch count. Indicator periods or settings.
Candle-close confirmation. Risk percent or lot size. Breakeven point. Partial-exit rules.
Hold time. Broker, spread or leverage.

## Cycle 1 — video 9bPlk7zSJAI, "$1400 in 2 hours SCALPING CRYPTO" (12:57)

Watched by subagent, which read his actual broker statement off the screen. The richest
measurement so far.

### BITCOIN IS HIS MASTER SWITCH — new, and now built

> "everything's based around bitcoin right so right here we saw a big fall in bitcoin look
> at dodge we saw a very similar fall look at litecoin a similar fall and look at xrp a
> similar fall so just remember **anytime bitcoin falls or gets pumped most other cryptos**
> especially like the bigger ones based around it **are going to pump up as well**"

He checks Bitcoin first and treats the alts as followers. Nothing in this project could
express that, because the portfolio runs each market in isolation and a strategy trading
XRP had no way to see BTC. Built as a class-level register: the instance handling BTCUSD
publishes its direction, the alt instances may only trade the same way, and an alt will
not trade at all without a recent read on Bitcoin.

### HIS CRYPTO WATCHLIST, read off his screen

Named "Crypto", exactly four symbols: **BTCUSD, DOGEUSD, LTCUSD, XRPUSD**.

The bot had BTC, ETH, LTC, XRP. **He holds DOGE, not ETH.** Fetched 10 months of DOGEUSD
15m (28,752 bars).

> "i'm actually going to be full time trading just **nasdaq us 30 gbp usd and all of my
> cryptos** and that's going to be it for now... because they all move similar and **the
> less you trade the more clear your mind is**"

### POSITION SIZE — measured off the statement, not spoken

Seven tickets, every one **0.5 lots**. Fixed, not risk-based. Deposit 5,000, profit
1,466.95, commission -24.50, balance 6,442.45 — **+28.85% of the account**.

### HE SCALES INTO ONE MOVE — measured

All seven entries inside a 322-point band, all seven exits inside a 32-point band, **the
whole basket closed at market within 47 seconds**. That is one decision in seven tickets,
not seven setups. Confirms the adding-to-a-winner mechanic with real fills.

And the exit was **a market sell, not a resting take-profit** — ticket visible on screen.

### STOP PLACEMENT — measured more precisely than he says it

> "i have my **stops pretty much just below** because if price breaks back down here most
> likely it's going to continue down"
> "**stops below the previous candle** is a good way to look at it as well"

Measured from the zoomed geometry: the entry sits at the open of the bullish breakout
candle, and the stop sits **below the swing low of the pullback, three to five candles
back** — not one tick under the signal candle. Stop width measured across five samples:
**254-574 points, 0.46%-0.99% of price, mean 0.61%.**

### HIS MEASURED RISK-TO-REWARD ON CRYPTO

Five drawn setups measured: **1.55, 2.35, 2.61, 3.53 and 1.93 — mean 2.39, median 2.35.**
So roughly **1:2 to 1:2.5** on crypto, not the 1:3 he quotes for indices or the 1:7 for a
small-account flip. He states no ratio at all in this video, so there is nothing to
contradict — but the number is his, off his own boxes.

### A TRAP THE SUBAGENT CAUGHT

Every stop box on his chart reads "Amount: 750", which back-solves to a TradingView
drawing tool configured for a $1,000 account risking $250. **That is a drawing-tool
setting, not his risk model.** His actual risk was fixed 0.5 lots — a 254-point stop is
$12.70, or 0.25% of his $5,000. Anyone reading those boxes as 25% risk would build
something wildly wrong.

### HE QUITS ON PROFIT — a daily rule not yet built

> "i'll wait for breakouts to get **quick profits that i can kind of just relax for the
> day after i get those profits**"

No loss limit or trade cap appears in this video; the day ends when he is up.

### SPREAD MATTERS HERE, measured

XRPUSD spread **19-47 points, median 33**, against stops of 254-574. That is **6-13% of
his stop** consumed by spread, plus $3.50 commission per 0.5-lot round turn. On a strategy
this tight the cost is not a rounding error.

### AND A WARNING FOR HOW TO READ HIM

The chart demonstration is TradingView **bar replay on March-April 2021 data**, while the
profitable trade on his phone is dated **21 September 2021**. The drawn examples are
250-1,350-point targets at about 1:2; the real trade held **4,190 points, 4.73%** — twelve
times the mean drawn stop. Whatever made the money was a runner held on a trailing stop,
not the 1:2 scalp he draws.

He says so himself: "i know i didn't break down too much of exactly how i trade word for
word tool for tool".

## Cycle 1 — video dOv1jOSsYLU, "How To Actually Make 6 Figures A Month" (16:51)

Watched by subagent, which read his LIVE ACCOUNT PANEL and a full week of his trade
history off the screen. This is the most consequential video watched so far, and not for
the reason the title suggests.

### HE HAS QUIT FOREX. INDICES ONLY.

> "let's go to **us30 NASDAQ only** let's **stay away from S&P** let's **stay away from
> gold** NASDAQ us30 let's stick there"
> "**indices is the way to go** it's the most liquid Market it moves the best it respects
> us the most... and that's part of the reason that I kind of **stopped trading Forex**
> because I've realized the Forex markets can be just a little bit **too manipulated**"

### HIS WINDOW IS THIRTY MINUTES, not 210

> "I don't know the last time I traded at **8 a.m.** was but it's probably been months...
> even by **7:00 a.m., 30 minutes in, I'm already getting ready to pack the books**"

Triangulated three independent ways off his own screen: his chart timezone is UTC-8, the
NFP release drop lands at 05:40 on it (8:30 ET = 5:30 PT, so the clock is Pacific), his
own trade opened at **06:49**, and his community win posts cluster at 6:58, 7:03, 7:22.
So 6:30 Pacific is the equity open and "30 minutes in" is literal.

Both windows are his -- 210 minutes from the futures video, 30 from this one. Built as a
parameter with a registered `mamba_indices` using 30, plus flattening open trades when
the window shuts: "we're here to **get in and get out**... the longer you're there the
worse your odds get."

### INTRABAR ENTRY, stated flatly

> "as it starts to break out **I do not wait for [candle] closure I get in as the market
> is pushing and breaking through**"
> "that'd be **right above these Wicks**"

### HIS SIZING RULE, measured from three of his drawn setups

| stop | target | ratio | quantity | risk | stop x qty |
|------|--------|-------|----------|------|-----------|
| 40.18 pts | 204.15 | 5.08 | 6 | $750 | 241.1 |
| 40.30 pts | 164.47 | 4.08 | 6 | $750 | 241.8 |
| 30.28 pts | 118.47 | 3.91 | 8 | $750 | 242.2 |

**Risk held constant at $750, quantity scaled inversely to stop distance.** That is
risk-per-trade sizing -- exactly what the bot already does -- and he never says it out
loud. Good news for once: the sizing model in the code is his, confirmed by measurement.

### AND THE THING THAT MATTERS MOST TODAY

His live "Last Week" history, six round trips, every one a sell, every one a win. Points
captured: **15.2, 7.2, 28.6, 37.6, 32.7, 2.8 — average 20.7 points.**

Against the **40-point stop he teaches**, that is an average of **0.5R**.

He narrates 1:4 and 1:5 all the way through the video — "if our stop-loss is 40 points and
our Target is for instance 160 points we call this a 1 to four", "we're easily able to hit
one to fives every single day", "you don't want one to ones, you don't want one to twos".

**His own statement says he takes about half a stop.** One trade held for one minute
(opened 06:49, closed 06:50).

This is not me disagreeing with him. It is a contradiction inside him, measured off his
own screen: **the targets he teaches and the exits he takes are irreconcilable.** A bot
built to his words is a 4R runner; a bot built to his statement is a sub-1R scalper. They
are different strategies and both are his.

Also measured: a 40-point stop on his $844,006 account at the volumes shown risks
**2.4%-4.7%**, far above the 1% he coaches students.

### NOT OBTAINABLE FROM HIM

His chart carries **8 indicators, legend permanently collapsed**, and he gates the
settings behind his paid mentorship — his community has a locked channel called
`secret-settings`. Also missing: touch count for a valid level, the exact breakeven
trigger, the partial trigger, any re-entry rule, any post-loss sizing rule.

## Cycle 1 — video 4JKwM9CeLig, "How I Made 3k In 1 Hour" (9:23)

Subagent read his Fibonacci levels, his indicator legend and his position boxes off the
screen and reconciled every number arithmetically. The most precise video yet.

### THE VOTE THRESHOLD IS NO LONGER MINE — HE COUNTS TO THREE

> "we hit the bottom of a channel so we know it's gonna push to the upside, we have
> bearish divergence showing **two confirmations** and now in **third confirmation** a
> fibonacci golden zone retest -- oh my god this trade's beautiful"

And he refuses a single one outright:

> "this isn't enough **we can't use just this as a confirmation**"

`min_votes` was 2, guessed by me, and flagged in every audit as the parameter with no
source. **His number is three, counted aloud while placing the trade.** Changed. It now
selects 11.6% of bars, against 2 selecting far more — a real filter rather than a
formality.

### HIS INDICATOR LEGEND, read off the screen

**EMA 8 close** (white), **MA 21 close** (orange, simple not exponential), and **OBV** in a
lower pane.

That is a different pair from the blank-chart video, which read out **SMA 8 and SMA 50**.
Both are his, from different videos. The 8 is constant; the slow line is 21 here and 50
there.

### OBV, NOT MACD — and OBV is now built

> "from here to here **lower low** look at the **obv higher low** that is a huge sign of
> reversal"
> "from here to here lower highs... from here to here higher highs that is a sign of
> bearish continuation"

MACD divergence went into this project on a single passing mention. **OBV is what is
actually loaded on his chart** and what he points at while explaining the trade. Added
`obv()` to the indicators and `obv_divergence()` as a signal; it fires on 19.8% of bars.

Note he calls the bullish case "bearish divergence". His label is wrong, his rule is not,
and the rule is what got built.

### HIS FIBONACCI LEVELS, exact

| level | note |
|-------|------|
| -0.618, -0.236 | extensions on the template, **never referenced** |
| 0 | the anchor high |
| 0.236, 0.382 | plain |
| **0.5** | **coloured gold** |
| **0.618** | **coloured gold** |
| 0.764 | **not 0.786** -- a non-default level |
| 1 | the anchor low |

The golden zone is 0.5-0.618 as already built. Two new facts: he uses **0.764 rather than
the standard 0.786**, and he never touches 0.705 or 0.79.

### AND A CORRECTION TO HOW I ANCHOR IT

> "take my Fibonacci I'm gonna **draw from this low to this high**"

Measured: he anchors on **wicks, not bodies**, and on the **bounce leg** -- the swing low
that just held the channel up to the first rally peak off it. That leg was **49.9 pips**.

`mamba_fib` finds the largest push in its window. He uses the small, most recent impulse.
Different thing.

### THE DOUBLE TOP IS A RED HERRING

> "I know a lot of you guys are asking, you see a double top, like why is this your entry"

He raises it only to dismiss the objection. The signal is channel touch plus divergence
plus golden zone. His double top is not a pattern he trades -- it is the thing he explains
away. That corrects the pairing I built earlier.

### BREAKEVEN WAS NARRATED, NEVER EXECUTED

> "once we hit you know 50 pips profit we're getting our stop losses to break-even anyways"

Measured: the stop box reads 1.07933 in every later frame. **It never moves.** So the
breakeven rule in the code is built from his words, not his chart -- worth knowing before
treating it as observed behaviour.

### HIS STOP AND HOLD, measured

Stop 30.3 pips, sitting **9.2 pips below the swing low**. Short trade: 45.2 pips. Position
boxes drawn to scale and the ratio labels honest -- 4.01 measured against 4.01 displayed.

Hold times: **~3h20m and ~6h**, across two calendar days. The title says one hour; his own
closing line says "two trades 300 pips in the span of one day". The 3k is $1,395 + $2,019
across both.

### AND A REGIME WARNING

The chart is **18-19 March 2020** -- peak pandemic volatility, EURUSD 1H candles with
110-pip ranges. A 30-pip stop and a 120-pip target are calibrated to that. They will not
transfer to a normal EURUSD, and he never says so.

## Cycle 1 — videos I2I4EVPFoak, qM4A_6i21I0 and qAvSFpKE4aE

Three more subagent reports. Between them they answer the question his own videos kept
dodging, and they contradict two things already in the code.

### THE ANSWER TO WHETHER HIS METHOD FITS $150

Measured off his phone: his broker prices US30 at **$100 per index point per lot**. So his
own minimum 0.01 lot on his signalled 25-point stop risks **$25 -- 16.7% of a $150
account**, far outside the "1-3% max risk per trade" printed on his own signals.

Leo's broker, checked directly on the account:

| symbol | 1 lot | 0.01 lot | 25-point stop | % of $150 |
|--------|-------|----------|---------------|-----------|
| **US30** | $1/pt | $0.01/pt | **$0.25** | **0.17%** |
| NAS100 | $10/pt | $0.10/pt | $2.50 | 1.67% |
| XAUUSD | $100/pt | $1.00/pt | $25.00 | 16.67% |

**His exact trade fits Leo's account and does not fit his own.** US30 has a hundred times
more headroom here than on his broker; NAS100 lands inside his 1-3% at minimum size; gold
is the one that cannot be done, which matches the fixed-lot danger found earlier.

### HIS POSTED SIGNAL — the most complete spec in the catalogue

Two of his own room cards, one buy one sell, identical geometry: **a flat 25.0-point stop
and a 1 / 2 / 3 / 4 / 6 R ladder**, unchanged by entry price or direction. His hit messages
confirm the arithmetic, and the footer reads "Please do not over risk! 1-3% max risk per
trade!" One signal per day. Built as `mamba_room.py`.

### HE HAS ABANDONED BREAK-AND-RETEST

> "the problem with this is **I'm waiting for that retest** and when you wait for that
> retest and it doesn't come you're **missing out on pips**, you're missing out on
> trades... **it just takes too long**"

He describes it in the past tense as the thing he stopped doing. That is exactly what
`mamba_retest.py` implements -- built from the $100-account video, which is older. Both are
his; this is the later word.

### AND HE DOES NOT TRADE THE BREAKOUT EITHER

> "it's a breakout pattern and for me **I don't like to trade the breakouts** necessarily
> but **the pre-breakouts** -- I like to get in there **before it breaks out** when I know
> it's going to break out so I can get as much pips as possible"

Measured: his fill sat **28 points above the support band with the trendline still 260
points overhead**. He bought at the level in anticipation, not on the break. That is the
opposite of every breakout entry in this project.

### THE SINGLE MOST CODEABLE THING FOUND ANYWHERE

His 5-minute chart carries about **twenty persistent horizontal levels** with price tags.
And every price in the trade snapped to one of them:

| his price | nearest drawn level |
|-----------|--------------------|
| entry 14085.25 | 14085.73 |
| TP1 14173.72 | 14171.26 |
| TP2 14242.28 | 14238.74 |
| TP3 14384.48 | 14384.18 |
| stop 14003.83 | 14003.75 |

**He builds the level map first, then selects entry, targets and stop from it.** Nothing in
this project works that way -- everything here computes a stop from a swing and a target
from a multiple. This is a different architecture and it is his.

### WHICH MEANS HIS TARGETS ARE NOT R MULTIPLES

Proof from his own cards: two gold entries at different prices carry **identical** TP1/TP2/
TP3 and stop, producing **2.62R on one and 4.44R on the other**. The prices are fixed to
structure; the ratio is whatever falls out.

That directly contradicts the fixed ladder in `mamba_room` -- which was measured off his
US30 room cards, where the spacing genuinely was a clean 1/2/3/4/6R. **Both are his, from
different videos.** Recorded rather than reconciled.

### ZONES ARE PIERCED, so triggers must read wicks

The daily wick went ~90 points through his zone and closed back inside; two of three
5-minute touches closed below the band. A bot testing "close inside the zone" would have
missed all three. **Wick interaction, not closes.**

### HIS ORDER OF TIMEFRAMES, frame-verified

5m glance, then **Daily, then H4, then back to 5m** to enter -- confirmed by the frames
matching his words second by second. His watchlist here, named "Scalping": **XAUUSD,
NAS100, US30, GBPUSD, GBPJPY.**

### HIS ACCOUNT PHASES, stated exactly

> "eventually I was able to turn a **100 account into a thousand**, thousand dollars into
> **ten thousand** -- I didn't want to go below ten thousand, start making like **two, 3K a
> month keeping my account 10,000, withdrawing anything above**, and then twenty thousand,
> thirty thousand, and I just kept doing this until I was at a six-figure account"

Cap the account, withdraw everything above the cap, then raise the cap. And after a
blow-up: "I kept losing, I kept creating more accounts."

### AND THE 1:1 IS A DECISION POINT, NOT AN EXIT

From I2I4EVPFoak: "once that gets hit, your main take profit gets it, **don't just take all
your profit** -- take a little bit of partials if you want, but better than that **trail
your stop loss, put that stop loss to break even**." Any bot exiting at 1:1 does the
opposite of what he teaches.

Also measured there: every ratio he speaks matches his tool exactly -- "one to seven point
five" against a displayed 7.51, "one to six" against 6.07, "one to almost five" against
4.48. **When he quotes a number off his screen he is accurate.** It is his *account* that
tells a different story from his *teaching*, not his arithmetic.

## Cycle 1 — video hGPg7_ZE1DM, "COMPLETELY FREE DAY TRADING COURSE" (18:58)

**The video contains no trading rules.** 0:00-7:10 is an advertisement for his Discord,
7:10-18:58 is a cigar-shopping vlog. He never opens a chart to teach, never draws a level,
never states an entry, a stop, a target or a risk figure. There is no new strategy in it.

Recorded because a null result is worth as much as a finding when the job is deciding
what to watch: **a video titled as a course can carry nothing**, and rule density has to be
measured rather than assumed from the title. Everything below was read off his screen
during the Discord walkthrough, not from his words.

### THIRD INDEPENDENT CONFIRMATION: he teaches high reward and takes low reward

Measured from his members' own trade screenshots in his win channel:

* stops: **28-34 index points** on US30 and NAS100
* runners: **45-84 points**
* so live risk-to-reward roughly **1.5-2.8 : 1**

against the **4.93 : 1** box he narrates over the same trade as a win.

That is now measured three separate ways from three different videos:

| source | what he teaches | what the numbers show |
|--------|-----------------|----------------------|
| his own live week, 6 trades | 1:4 and 1:5 throughout | **0.5R average** |
| his NAS100 $250k trade | 3.68R planned | exited **2.90R**, "I got out early" |
| his members' fills | 4.93R narrated | **1.5-2.8R** |

**He is consistently more conservative in the execution than in the teaching.** Not a
contradiction I am inventing to justify a change -- it is the same gap measured from his
account, his trade and his community, independently.

### THE TARGET LADDER IS ~1R EQUAL STEPS — measured, and it corroborates mamba_room

Pixel-measured inside his reward boxes: rungs at 0.83R, 1.61R, 2.74R with even spacing of
**0.87R per step** on one setup, and a clean **1.0R ladder** fitting every line on another.
The number of rungs varies per trade (3 to 5+), which is why the total varies while the
spacing does not.

`mamba_room` was built from his posted cards as 1/2/3/4/6R. Equal ~1R steps with a varying
final rung is the same shape, arrived at from different evidence.

### HIS NEW YORK WINDOW IS TIGHTER STILL

Member fill timestamps cluster **16:30-16:37 broker time** -- the first **seven minutes**
after the 09:30 ET cash open. One member held a US30 trade for **53 seconds**.

So there are now three widths from him: 210 minutes (futures video), 30 minutes (indices
video), and a ~7-minute cluster in his own room. All his.

### AND HIS OWN CHART HERE IS COMPLETELY BARE

Candles plus one horizontal line. **No moving averages, no volume pane, no oscillator.**

That is a third distinct indicator setup: SMA 8 and 50 in the blank-chart video, EMA 8 with
MA 21 and OBV in the 3k video, eight collapsed studies in the six-figures video, and
nothing at all here. His chart is not a fixed thing.

### THREE SESSIONS, confirmed again

> "in the live trading room, we trade **New York session, Tokyo session, and London
> session**" / "you're getting **three live trading sessions** every single day"

### AND THE MAP OF HIS METHOD, read off his course channel

Thirteen sections: start now · where to trade · what to trade · contracts and ticks ·
analyzing time frames · price action and market structure · support and resistance ·
sessions to trade · **volume** · **using data** · **stop loss adjustments** · psychology ·
trading account guide.

None of it plays in this video, but it names the parts he considers the method -- and
"stop loss adjustments" being its own section confirms that moving stops is central rather
than incidental.

## Cycle 2 — his level map built, and it is a different architecture

`level_map()` and `snap_to_level()` in `mamba_patterns.py`.

He does not compute a stop from a swing or a target from a multiple. He draws the
horizontal levels first and then picks entry, stop and targets off that map. Proven on
the $250k trade, where all five prices matched lines already on his chart:

| his price | drawn level | gap |
|-----------|-------------|-----|
| entry 14085.25 | 14085.73 | 0.5 pts |
| TP1 14173.72 | 14171.26 | 2.5 |
| TP2 14242.28 | 14238.74 | 3.5 |
| TP3 14384.48 | 14384.18 | 0.3 |
| stop 14003.83 | 14003.75 | 0.1 |

Built from wick extremes rather than closes, because his zones get pierced -- a level is
where price REACHED, not where it settled. Clustered so a level is a band several wicks
returned to, ranked by attendance, handed back in price order so a caller can walk the map
up or down.

Verified on US30 15m: **24 levels** where he had about twenty, and a level within range on
**93% of bars**.

### Why this matters more than any single rule

Every knob still flagged as mine exists because there was no map to select from --
`stop_bars`, `target1`, `target2`, `fallback_reward`, `trail_after`. With a map, those are
answering a question he never asks. `snap_to_level` returning None is itself the answer in
the case they were invented for: **no level in range means no target he would have drawn,
so there is no trade** rather than a number I made up.

That is the route to deleting the rest of them rather than tuning them.

## Cycle 2 — his architecture built and registered as `mamba_levels`

Selects rather than computes. No stop distance is configured: the stop is the level below
entry. No target multiple: the target is the next level up the map, and when the map has
nothing in range there is **no trade** rather than a fallback ratio.

**The evidence it is right:** with no width and no ratio set anywhere, it produces **22-28
point stops at 1:1.9 to 1:2.8** on US30. His measured live trades sit at **28-34 point
stops, 1.5-2.8R**. The map reproduces his numbers without being told them, which is what a
faithful architecture should do and what no amount of tuning a `stop_bars` knob achieved.

And the ratios differ trade to trade, as his do. Two of his gold entries carried identical
targets and produced 2.62R and 4.44R — impossible if the targets were multiples.

Fires on 8.8% of sampled bars.

## Cycle 2 — a real constraint on the parallel plan

Six subagents launched at once and **all six died on server overload (HTTP 529)**, as did a
seventh on retry. The plan assumed the only limit on watching all 162 was doing them one at
a time; there is a second limit, which is how many can run at once before the API refuses.

Not retried immediately, because relaunching into an overloaded service makes it worse.
Working solo in the meantime and dropping the fan-out width when it resumes.

Honest revision: **all 162 in eleven hours is not achievable at this fan-out**. Two or three
agents at a time is likely the practical ceiling, which is perhaps 30-50 videos in the
window rather than 162. The tracker means the next run continues rather than restarts.

---

# THE TWENTY DIMENSIONS — his answer, from 18 videos watched properly

Required by the prompt before stopping. Each has his own words, or NOT FOUND YET.
Where he gives different answers in different videos, all are recorded — the
inconsistency is his, and choosing between them would be me overriding him.

**1. MARKETS.** "full time trading just nasdaq us 30 gbp usd and all of my cryptos".
Later and narrower: "us30 NASDAQ only, stay away from S&P, stay away from gold" plus
"I kind of stopped trading Forex because the Forex markets can be too manipulated".
His crypto four, read off screen: BTC, DOGE, LTC, XRP. Watchlists seen: "Scalping"
(XAUUSD, NAS100, US30, GBPUSD, GBPJPY) and "Scalping BIG" (adds UK100, FRA40, NQ1!,
YM1!). One pair he singles out: "GJ is what I'm going to be trading for the rest of
my life".

**2. SESSIONS AND CLOCK.** "you only trade during New York session... around 6:20,
6:30 a.m." — his clock is UTC-8, triangulated three ways. Three different widths,
all his: 210 minutes ("I don't like to trade much past 10:00 a.m."), 30 minutes
("even by 7:00 a.m., 30 minutes in, I'm getting ready to pack the books"), and a
7-minute cluster in his own room's fills. Plus "Tokyo session for me is better for
gold", and his room runs "New York session, Tokyo session, and London session".

**3. TIMEFRAMES AND ORDER.** "we're gonna start on the h4, always h4 — you can use
the daily as well, I like the h4." Full sequence frame-verified once as Daily → H4 →
5m. The daily's job is a veto: "we check our daily to make sure that that's the
case". Entry timeframe is 5m or 1m: "it's very important that you use a 5-minute or
1-minute chart simply because we are super scalping". And "don't use the hourly as
much".

**4. INDICATORS.** Four different setups across four videos, all his: SMA 8 and SMA
50 ("that's all we're going to be using", "simple ones are a lot better"); EMA 8
with MA 21 and OBV; eight collapsed studies gated behind his paid room; and a
completely bare chart. Where he gives settings they are exact — RSI period 14 with
bands at 75 and 25, Bollinger period 34. The 50 he names in 22 separate places.

**5. HOW HE FINDS A LEVEL.** The answer that reorganised the whole build: he draws a
map of horizontal levels first. "right here we have resistance — boom boom boom boom
boom". Level types: swing extremes; congestion, which he calls a buildup ("it's just
a buildup in the moment off a bunch of candles — it's a buildup zone, it's
support"); parallel channels; trendlines; Fibonacci; supply and demand zones. On
touches: "resistance and support lines do not need to be perfect", two is enough,
and measured drawings show 3-4. Zones get pierced — triggers must read wicks, not
closes.

**6. WHAT TRIGGERS THE ENTRY.** He rejects both of the obvious ones. Retest:
"waiting for that retest... it just takes too long" — past tense, abandoned.
Breakout: "I don't like to trade the breakouts necessarily but the pre-breakouts —
I get in there before it breaks out". Measured: he bought 28 points above support
with the trendline still 260 points overhead. And no candle close: "I do not wait
for closure, I get in as the market is pushing and breaking through".

**7. HOW HE PICKS DIRECTION.** "first off I need to determine, are we going up are
we going down... that's going to be from the daily and the four hour." Simplest
statement: "I'm going to take a sell if we're in a selling market and I see a
support break." Bitcoin gates the alts: "anytime bitcoin falls or gets pumped, most
other cryptos are going to pump up as well".

**8. CONFLUENCE.** THREE, counted aloud: "we have bearish divergence showing two
confirmations and now in third confirmation a fibonacci golden zone retest". And he
refuses one: "this isn't enough, we can't use just this as a confirmation".

**9. STOP PLACEMENT.** "stops are right above the highs" / "below that previous
support line". Measured, it is the level below entry, and below the swing low of the
pullback rather than one tick under the signal candle. Widths he states: 10, 13, 16,
22, 25, 30, 40, 44 pips, and "15 pips 20 pips at the most" on gold. His stated key:
"super, super tight stop losses". Mental stops exist — "my mental stop losses are
very very tight" — and are not buildable server-side.

**10. TARGETS.** Not multiples. Measured proof: two gold entries with identical
targets produced 2.62R and 4.44R. "I'll target my next main zone" / "we can always
take profit way up here at this major resistance zone". Ratios he quotes span 1:1 to
1:10 depending on the trade: 1:1 on the scalper, 1:3 on indices, 1:4-1:5 on futures,
1:7-1:10 flipping a small account. And the 1:1 is a decision point, not an exit:
"don't just take all your profit... trail your stop loss, put that stop loss to
break even".

**11. POSITION SIZE.** Fixed cash risk with size scaled inversely to stop distance —
measured on three separate videos, always the same $750 in his drawing tool. He
never says it out loud. His stated percentages: "three to five percent max"
carefully, then "risking 10%", "risking 15%", "risk 25% of your account, which is
kind of what you're going to have to do" for a small account. His own signals print
"1-3% max risk per trade". And on a small account, a fixed lot: "if you're using a
0.01 that would have been a dollar sixty loss for a five dollar and 10 cent gain".

**12. TRADE MANAGEMENT.** Breakeven at 1:2 — "we got to a 1 to two, stops can go to
break even" — and "near break even" rather than exactly. Half off: "I'm gonna take
half my profits here". Trailing: "I'm going to trail my stop-loss all the way up",
walked level to level. Adding to a winner: "we're doubling up on that position",
confirmed by seven tickets in one basket. Never widens a stop — zero mentions in 144
transcripts. Caution: on one video the breakeven was narrated and the stop box never
moved.

**13. HOLD TIME.** "you get in, you get out, you move on — you don't hold trades for
a long time", narrated at "30 minutes, 35 minutes at the most". Measured holds range
from 53 seconds and 1 minute up to 3-6 hours, and a 5-day gold carry on the same
account. The 1-minute chart is faster still: "you got to get in, you got to get out
quick, they reverse fast".

**14. EXITS.** Target reached; stop; trailed stop taken out in profit; the level
ahead — "price at a strong resistance zone... I just want to get in and out";
uncertainty — "I ended up closing because I wasn't sure if price was going to fully
reverse"; the reason dying — "trend got broke, it's not going to come back"; the
clock — "getting later in the day, pack the books"; satisfaction — "I got out early
but it kept going"; and memory of a shape that burned him — "last time this
happened I got stopped out, let me just get out early".

**15. RE-ENTRY.** Yes, but conditionally: "I'm not going to continue to re-enter
unless that trading strategy says it's still a good trade". After leaving early: "I
got out too early, I want to re-enter this trade" — which he numbers as "trade
number two part two". Every re-entry he narrates follows him closing, never being
stopped out.

**16. DAILY LIMITS.** "my rule is I can only take three trades max in one day... I
say three but I think two is better... really after two losses you should stop and
wait till the next day." Also quits on profit: "quick profits that I can just relax
for the day after". His forbidden ceiling: "you cannot go out there and take 30
trades in one night".

**17. AFTER A LOSS.** "wait till the next day, let the markets refresh, get your
psychology back on track and then trade again." No size change stated anywhere. He
warns against revenge trading and against watching the balance: "never look at the
money in your account... look at the chart itself".

**18. ACCOUNT PHASES.** Exact: "turn a 100 account into a thousand, thousand into
ten thousand — I didn't want to go below ten thousand, keeping my account 10,000,
withdrawing anything above, and then twenty thousand, thirty thousand". Cap,
withdraw above the cap, raise the cap. On blowing up: "if we do lose it, that's
okay, we deposit again" and "I kept losing, I kept creating more accounts". Once
grown: "you do 5% per week".

**19. WHAT HE REFUSES.** Trades into strong opposing structure — "we're at a pretty
strong resistance here, so no, not the smartest trade". S&P and gold on the indices
build. Forex entirely, latterly. The retest. 1:1 targets. Overtrading, in many
forms. Switching strategies: "don't go around looking for other strategies... it
just messes up the entire strategy". And believing anyone who claims no losses:
"whoever your mentor is is lying to you".

**20. HIS CONDITIONS.** Zero-spread accounts: "there's no spread, it's pretty much
zero" / "when I enter that trade I am instantly in profit, if not at break even,
because there's no spread at all". Measured: US30 spread 1.40 points on his live
panel, NAS100 1.90, XRP 33 points. Commission $0.70 per unit round turn. His broker
prices US30 at $100 per point per lot. Platforms seen: MT4/MT5 mobile, Match-Trader,
Liquid Trader Pro, TradingView for charting. He recommends MT5 for its drag-to-move
stop.

## NOT FOUND YET

* The settings of the eight indicators on his six-figure chart — gated behind his
  paid room, and a channel there is literally called secret-settings.
* Any numeric touch count. He says "a couple" and "not perfect"; drawings show 3-4.
* The precise trigger point for his breakeven move and his partials, beyond "at some
  point" and "getting a little later in the day".
* Any post-loss sizing rule.
* Whether the level map is redrawn intraday or set before the session.

## Cycle 3 — the parameter audit, and the first real deletions

92 distinct parameters across the mamba strategies. **50 now carry his quote; 42 do not.**
The prompt's rule is that an unsourced parameter gets deleted rather than explained, so
here is the first pass of that, plus an honest note on which of the 42 are actually
framework rather than trading decisions.

### DELETED

**`use_ma`, the side-of-the-average vote.** Price is always on one side of a moving
average, so it voted on **100% of bars** — a free vote that quietly made a threshold of
three mean "the average plus any two other things". And he never asks the question it
answered: he does not say "price is above the 50, so buy", he names two events, the
crossover and the swoop. A state he never reads is not a rule of his. Gone, not defaulted
off.

**MACD divergence.** It entered this project on a single passing mention while **OBV is
what is actually in his chart legend** and what he points at while explaining a trade.
Two divergence signals voting is one of them carrying weight he never gives it.

Result, measured after the deletions:

| signal | fires |
|--------|-------|
| gap | 56.3% |
| swoop | 27.1% |
| double top | 25.3% |
| OBV divergence | 19.8% |
| liquidity sweep | 15.7% |
| buildup | 12.6% |
| engulfing | 3.6% |
| MA crossover | 2.6% |

**No signal fires on 100% of bars any more.** His counted floor of three agreeing now
selects **6.2%** of bars — genuinely picky, where before the free vote made it far looser.

### HONEST NOTE ON THE REMAINING 42

Not all of them are trading decisions. `timeframe`, and the various `lookback` fields are
framework plumbing; `boll_stdevs` is a TradingView default he leaves untouched, which is
arguably his by omission; `open_hour_utc=14` is in fact sourced — "around six o'clock in
the morning" on his UTC-8 clock — and my table simply missed it.

The genuinely unsourced ones that shape a trade are the stop geometry (`stop_bars`,
`stop_beyond_pct`, `stop_zone_frac`, `stop_buffer_pct`, `stop_candle_frac`), the target
geometry (`target1`, `target2`, `target_pct`, `fallback_reward`), the Fibonacci anchoring
(`push_bars`, `min_push_pct`), the trend windows (`trend_bars`), the trail distance
(`trail_after`), and every number in `mamba_channel` (`edge_pct`, `stop_pct`,
`min_width_pct`, `touch_tolerance`).

**All of those exist because there was no level map.** With `mamba_levels` the stop is the
level below entry and the target is the next level up, so the geometry knobs answer a
question he never asks. Deleting them means migrating the older strategies onto the map
rather than editing a default — which is the next job, and a refactor rather than a
find-and-replace.

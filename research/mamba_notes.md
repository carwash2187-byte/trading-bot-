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

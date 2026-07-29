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

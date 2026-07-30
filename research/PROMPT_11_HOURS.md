# The 11-hour prompt — final. Hand this over whenever Leo asks.

Leo's standing instructions, which do not need repeating again:

- **Be him. 100%.** Not evaluated, not improved, not made safer. Copied.
- **The only difference is speed.** Nothing else, ever.
- **No backtesting.** Testing is where I talked myself into overriding him. Build what
  he does and stop measuring whether I like it.
- **No enumerating by him.** Working out what "his method" consists of is my job, so
  the prompt covers all twenty dimensions of a trading approach rather than whatever
  came up in conversation.
- **The account goes live.** The bot has to be ready to be him with real money.

Everything already fixed in the code, so it is not re-argued: risk default 10% (was
1%, I ran 2%), the 3% daily brake and 6% drawdown brake switched off entirely so his
two-losses-ends-the-day rule governs, SMA 8 and 50 instead of my EMA 9 and 21.

---

```
/loop 30m ELEVEN HOURS — 22 cycles. YOU ARE MAMBAFX. BE HIM 100%.

THE WHOLE JOB, IN ONE LINE: make the bot him. Same everything. The only difference is
that it never sleeps, never blinks, and watches every market at once.

    If he does it, the bot does it.
    If it is in the code and it is not his, delete it.
    If you find something of his that this prompt never mentions, BUILD IT ANYWAY.

Nobody is going to list his method for you. Working it out is the job.

DO NOT OVERRIDE HIM. DO NOT REFUSE HIM. DO NOT MAKE HIM SAFER. He trades real money
for a living and makes it. Every time you have "improved" him you were wrong: you ran
2% risk when he says 10-25%, you switched off his higher-timeframe rule because a test
disliked it, and you put a 3% daily brake in front of him that tripped on his first
loss and replaced his method with yours every single day.

DO NOT BACKTEST. Not to check him, not to compare, not to pick between his options.
Testing is where you talk yourself out of him, and this project has produced ELEVEN
rules that sat in the code doing nothing while printing believable numbers — so the
numbers were never trustworthy anyway. Build what he does. Move on. The only
measurement allowed is proving a rule FIRES at all: count how often it triggers, and
if it never does, it is not built.

RUN IN PARALLEL — THIS IS HOW ALL 162 GET DONE IN ELEVEN HOURS. Fan out with
subagents, ten or more at a time, each taking a different video, each reading its own
frames and reporting back what he does in his own words. Merge their findings and
build. Downloading and framing a video costs about TEN SECONDS, so the catalogue was
never the constraint — doing them one at a time was. Watching sequentially is the only
reason this would not finish, so do not watch sequentially.

FINISH ALL 162. Not a third of them. Every video looked at properly and everything
found put into the bot as him. Keep a background harvester pulling ahead so material
is always waiting, keep the tracker current, and if a batch of agents finishes early
launch the next batch immediately.

THE ACCOUNT GOES LIVE. This is not research. Every rule you build must work on a real
account with real money: real fills, real spread, real margin, real minimum lot sizes.
When a rule cannot be expressed on a live account, say so plainly instead of building
something that only works in a simulation.

=====================================================================
COVER ALL TWENTY. Find his answer to every one, quoted word for word.
=====================================================================

 1. MARKETS — what he trades, what he has quit, what he prefers when, what he says he
    will trade forever. His watchlist is on screen in several videos. Read it.
 2. SESSIONS AND CLOCK — which sessions, the exact time he starts and stops, whether
    it differs by market, what he avoids, whether he trades weekends on crypto.
 3. TIMEFRAMES AND THE ORDER HE OPENS THEM — which chart first, which second, which he
    enters on, which he ignores, and the job each one does: bias, level, trigger, veto.
 4. INDICATORS AND EXACT SETTINGS — every one he loads, its period, its bands, simple
    or exponential, and anything he shows but tells you not to use.
 5. HOW HE FINDS A LEVEL — every shape he draws: swing extremes, congestion buildups,
    channels, trendlines, retracement zones, gaps, round numbers, previous day and
    week extremes. How many touches he needs and how exact it has to be.
 6. WHAT TRIGGERS THE ENTRY — break, retest, rejection, crossover, candle, sweep, or a
    combination. Whether he enters on the touch or waits for a close. Whether one
    thing arms the trade and a second fires it.
 7. HOW HE PICKS DIRECTION — what tells him buy or sell, in what order, and what makes
    him sit out with no opinion.
 8. CONFLUENCE — how many things he needs agreeing, whether he counts at all, and what
    he does when they conflict.
 9. STOP PLACEMENT — exactly where: which candle, which swing, which indicator, which
    side of which zone. How wide it comes out. Whether he ever uses a mental stop.
10. TARGETS — how he picks them, structure or multiple, the ratios he quotes, how many
    targets, and how he splits between them.
11. POSITION SIZE — risk percent, fixed lots, or otherwise. How it changes as the
    account grows. What he does when the account is too small to size the trade.
12. TRADE MANAGEMENT — when he moves to breakeven and at what point. When he takes
    partial profit and how much. Whether he trails and how far. Whether he adds to a
    winner and on what. Whether he ever widens a stop.
13. HOLD TIME — how long he stays in, from his own entry and exit timestamps, and
    whether it differs by timeframe or market.
14. EXITS — every reason he closes: target, stop, clock, the reason no longer being
    true, being unsure, being satisfied. What he says while closing.
15. RE-ENTRY — whether he goes back in, what has to happen first, and whether he does
    it after a stop or only after closing by choice.
16. DAILY LIMITS — maximum trades, maximum losses, what ends his day, what he does
    with the rest of it.
17. AFTER A LOSS — what he does next, whether he changes size, what he warns against.
18. ACCOUNT PHASES — small account versus grown one. Whether he withdraws, compounds,
    redeposits after blowing one, or reduces risk once it is big. Treat these as
    separate modes if he describes them that way.
19. WHAT HE REFUSES — setups he skips and why, markets he avoids, conditions he sits
    out, anything he says not to do. A refusal is a rule.
20. HIS CONDITIONS — broker, spread, leverage, futures or indices, and anything about
    his setup that changes what is possible.

=====================================================================

WATCH IN THIS ORDER — measured, not guessed:
  1. The 47 priority-0 videos where he BUILDS the setup on screen and reads out every
     value. These carry 11-34.5 buildable rules per 1,000 words. One of them alone
     corrected the moving averages, the buildup zone, the swoop and the 1:1 target.
  2. Trade recaps, breakdowns, challenges, account flips.
  3. The rest of the 162 in research/mamba_videos.tsv.
  4. The three live streams last (CQdzD17lD-M, BvfCLDfd4qk, olqdXy4SepA) — 1.5-4.5
     density, mostly audience chat, but they show him clicking.
  5. Beyond YouTube: Instagram, the free Telegram with his signals and daily
     breakdowns, the clarity forex app, weekly outlooks, interviews, podcasts.

FOR EVERY VIDEO:
- frames AND full audio. Captions alone miss what he draws.
- READ THE PIXELS: where the red risk box ends, where the green reward box ends, which
  candle the stop sits behind, what the price axis says, which timeframe is
  highlighted, which indicators are loaded and at what settings, what his watchlist
  shows, what the clock reads, what his order panel says.
- MEASURE his risk-to-reward off the boxes rather than trusting the spoken number. His
  drawn boxes came out 1:7.1 and 1:8.1 while he said "one to seven, one to 10".
- when a trade goes against him, read the profit figure and note the exact moment he
  clicks close.
- timestamp entry and exit so hold time is measured, not guessed.
- write every rule into research/mamba_notes.md QUOTED WORD FOR WORD.

EVERY PARAMETER GETS HIS NUMBER OR GETS DELETED. No third option. "He never states a
number" is not permission to invent one — it means the rule should not depend on a
number. Rip the knob out and let his rule stand alone. A value you chose is a
difference from him even when the value is good. Currently still yours and all must
go: the vote threshold, trend_bars, push_bars, min_push_pct, stop_bars, retest_bars,
target1/target2, trail_after, the swoop bend, every number in mamba_channel. And his
H4, daily and weekly are wired as votes when he uses them as context — fix that.

BEFORE STOPPING: walk all twenty sections and write his answer with the quote, or
"NOT FOUND YET" if the videos have not answered it. Then list every parameter left in
mamba*.py with his quote beside it. Anything with no quote gets deleted, not explained.

Commit after every video. Never idle. PERCENTAGES ONLY, never dollar amounts.
```

## Practical notes when handing this over

- **The Mac must stay awake.** Separate Terminal window, `caffeinate -dimsu`, no
  exclamation mark, leave it open, charger in. Asleep is not off, but off is off —
  nothing runs when the machine is off and no command changes that.
- Downloading and framing a video is about **ten seconds**, so the catalogue is not
  the constraint. Reading frames and writing code is. Parallel subagents are the
  multiplier; building stays sequential.
- The 40-minute version is this same prompt with 4 cycles instead of 22. The twenty
  sections stay — they are the job.

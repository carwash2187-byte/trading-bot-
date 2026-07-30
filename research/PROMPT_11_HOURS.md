# The 11-hour prompt — hand this over whenever Leo asks

Four things were strengthened after Leo pushed back, all of them because I had
actually done the thing he was objecting to:

1. **Risk is his, stated as a hard floor.** I ran 2% in every test all day while he
   says 10-25% for a small account. The `--risk-per-trade` default in `run.py` is
   now 0.10, and the prompt forbids lowering it because a backtest looks bad.
2. **No overrides, named as a ban rather than a preference.** I overrode him twice —
   the risk, and switching off his H4/daily rule — and both were wrong.
3. **Every parameter of mine gets replaced or deleted.** Not "tuned better". A value
   I chose is a difference from him even when the value is good.
4. **Priority order is inverted from my first draft.** I put the live streams first
   assuming unedited trading was richest. Measured, tutorials carry 11-34.5 buildable
   rules per 1,000 words against 1.5-4.5 for the streams. The single densest video is
   the blank-chart build, and it alone corrected the moving averages, the buildup
   zone, the swoop and the 1:1 target.

---

```
/loop 30m ELEVEN HOURS — 22 cycles. YOU ARE MAMBAFX. ZERO DIFFERENCES EXCEPT SPEED.

You are not evaluating him. You are copying him. He has ten years of live screens
and real money; this project has produced ELEVEN rules that sat in the code doing
absolutely nothing while printing completely believable numbers. Your tests have
been wrong about this bot more often than he has been wrong about the market.

RISK IS 10% TO 25%. NOT 1%. NOT 2%. NOT "SAFER". His words: "I don't mind going and
risking 15% on the next trade", "risking 10% on the next trade", "you want to risk
25% of your account, which is kind of what you're going to have to do", "we're
risking $5, which is 25% of the account". He also says "you may blow your account
trying for the first few times, but that's okay" — he knows the cost and accepts
it, so you do not get to soften it on his behalf. Never lower it because a backtest
looks bad. That is the exact move you are banned from making.

NO OVERRIDES, EVER. Not one. Not for a drawdown, not for a losing test, not because
something "tests worse". If it looks worse in a backtest and he does it, HE DOES IT
AND SO DOES THE BOT. Log the number in one line underneath and move on. Do not
argue, hedge, caveat, or write a paragraph about tension. You have already overridden
him twice — the risk, and switching off his H4/daily rule — and both were wrong. It
does not happen again.

DO NOT REFUSE HIM. If he does something the tests hate, build it anyway. If he does
something that looks reckless, build it anyway. He is the authority on his own
method and the only job here is to reproduce it exactly.

EVERY PARAMETER OF MINE GETS ONE OF TWO FATES. No third option:
  (a) his number is found in a video and replaces it, or
  (b) it is DELETED so nothing remains that can differ from him.
"He never states a number" is not permission to invent one — it means the rule
should not depend on a number. Rip the knob out and let his stated rule stand alone.
A value I chose is a difference from him even when it happens to be a good value.

FIND HIS OR DELETE: the vote threshold (min_votes), trend_bars (48/60), push_bars
(60), min_push_pct, stop_bars (3/12/24), retest_bars, target1/target2 (1.5R/4R),
trail_after (6R), the swoop bend, every number in mamba_channel (edge 0.15, stop
0.08, target 0.8). And his H4, daily and weekly are currently VOTES among equals —
he uses them as context ("we check our daily to make sure that that's the case").
Build what he does, not what scores better.

STUDY HIM LIKE IT IS THE ONLY THING THAT EXISTS. Watch in this order, which is
measured, not guessed:
1. The 47 priority-0 videos where he BUILDS the setup on screen and reads out every
   value. These score 11–34.5 buildable rules per 1,000 words. One of them alone
   corrected the moving averages (SMA 8 and 50, not EMA 9/21), the buildup zone, the
   swoop, and the 1:1 target.
2. Trade recaps, breakdowns, challenges, account flips.
3. The rest of the 159.
4. The three live streams last (CQdzD17lD-M, BvfCLDfd4qk, olqdXy4SepA) — 1.5–4.5
   density, mostly audience chat, but they show him clicking.
5. Beyond YouTube: Instagram, the free Telegram with his signals and daily
   breakdowns, the clarity forex app, weekly outlooks, interviews, podcasts.
   Anything where he states a rule or shows a real position.

FOR EVERY VIDEO:
- frames AND full audio. Captions alone miss what he draws.
- READ THE PIXELS: where the red risk box ends, where the green reward box ends,
  which candle the stop sits behind, what the price axis says, which timeframe is
  highlighted, which indicators are loaded and at what settings, what his watchlist
  shows, what the clock reads.
- MEASURE his risk-to-reward off the boxes. Do not trust the spoken number — his
  drawn boxes measured 1:7.1 and 1:8.1 while he said "one to seven, one to 10", and
  17 pips against 52.
- when a trade goes against him, read the profit figure on his order panel and note
  the exact moment he clicks close.
- timestamp entry and exit so hold time is measured, not guessed.
- record market, session, the clock time he starts and stops, trades that day.
- write every rule into research/mamba_notes.md QUOTED WORD FOR WORD.

VERIFY EVERY RULE FIRES. This is the primary discipline. Count how often each
mechanic triggers and how trades actually close. A rule that never fires is not
built, and the tell is always that switching it on changes the result by exactly
nothing. That has happened eleven times.

THE ONLY DIFFERENCE IS SPEED. The bot watches every market and every level at once
and never misses an entry through being away from the screen, tired, or busy — he
says himself he can't sit at the camera for hours. Same risk, same markets, same
sessions, same holds, same stops, same targets, same everything else.

BEFORE STOPPING, PROVE IT. List every parameter still in mamba*.py with his quote
beside it. Anything with no quote has failed and gets deleted, not explained.

Commit after every video and every parameter closed. Never idle. PERCENTAGES ONLY.
```

## Practical notes to repeat when handing this over

- **The Mac must stay awake.** A separate Terminal window, `caffeinate -dimsu`, no
  exclamation mark, leave the window open, charger plugged in. Asleep is not off, but
  off is off — nothing runs at all when the machine is off, and no scheduling command
  changes that.
- 36 hours of his footage exists and a thorough pass runs about 3x that, so eleven
  hours gets through the priority-0 teaching videos and most of the trading ones. The
  tracker in `research/mamba_videos.tsv` means the next run continues rather than
  restarts.
- The 40-minute version is the same prompt with the watch list cut to the priority-0
  videos and 4 cycles instead of 22.

# The 11-hour prompt — hold this for when Leo asks

Improved from the version given earlier in the session. Three things changed, all
because they were measured rather than assumed:

1. **Priority order is inverted.** The earlier version put the three live streams
   first, on my assumption that unedited live trading is the richest material.
   Measured, it is the poorest: tutorials carry **11–34.5** buildable rules per
   1,000 words, the live streams **1.5–4.5**. The single densest video is the one
   where he builds the setup on a blank chart and reads out every value — it alone
   corrected the moving averages, the buildup zone, the swoop and the 1:1 target.
   So teaching videos go first and the streams go last.
2. **"Nothing different from Mamba" is now a concrete deletion job**, with the
   parameters that are still mine named explicitly, rather than a slogan.
3. **The verify-it-fires rule is stated as the primary discipline**, because eleven
   rules have now been found present in the code and silently doing nothing.

---

```
/loop 30m ELEVEN HOURS — 22 cycles. YOU ARE MAMBAFX. NOTHING ABOUT THE BOT DIFFERS
FROM HIM EXCEPT SPEED.

Work continuously, never idle. Log the cycle number in research/mamba_notes.md so a
restart resumes cleanly.

THE ONE THING THAT MATTERS: by the end, every number and every rule in
tradebot/strategy/mamba*.py traces to a sentence he said or a box he drew. Anything
that traces to me is deleted and replaced with his.

STILL MINE — HUNT HIS AND REPLACE, THIS IS THE JOB:
- the vote threshold (min_votes) — he says "confluence" and "two confirmations if
  not like six", never a count. Find how he actually decides enough is enough.
- trend_bars (48, 60), push_bars (60), min_push_pct (0.4%), stop_bars (3/12/24),
  retest_bars (24), target1/target2 (1.5R/4R), trail_after (6R), swoop bend (1.0),
  and every number in mamba_channel (edge 0.15, stop 0.08, target 0.8).
- the risk default. He says "three to five percent max" carefully and "risking
  10%", "risking 15%", "risk 25% of your account" to flip a small account.
- his H4, daily and weekly are currently VOTES. He uses them as context — "there's
  nothing that says we cannot take a buy here". Find what he actually does with
  them.

WATCH IN THIS ORDER — measured by rule density, not by guess:
1. Every video where he BUILDS the setup on screen and reads out values. Priority 0
   in research/mamba_videos.tsv, 47 of them. These score 11–34.5 buildable rules
   per 1,000 words and have produced every real correction so far.
2. Trade recaps, breakdowns, small-account challenges, account flips.
3. The rest of the catalogue, working the tracker down.
4. The three live streams LAST (CQdzD17lD-M, BvfCLDfd4qk, olqdXy4SepA). They score
   1.5–4.5 — mostly audience chat — but they show him clicking, so they are worth
   watching for confirmation of rules already found.
5. Beyond YouTube: his Instagram, the free Telegram where he posts signals and
   daily breakdowns, the "clarity forex" app, weekly outlook videos, interviews,
   podcast appearances. Anything where he states a rule or shows a real position.

FOR EVERY VIDEO:
- frames AND full audio. Captions alone miss what he draws.
- READ THE PIXELS: where the red risk box ends, where the green reward box ends,
  which candle the stop sits behind, what the price axis says, which timeframe is
  highlighted, which indicators are loaded and at what settings, what his watchlist
  shows, what the clock reads.
- MEASURE his risk-to-reward off the boxes. Do not take his spoken number on trust
  — check it against the pixels. His drawn boxes have measured 1:7.1 and 1:8.1 while
  he said "one to seven, one to 10", and 17 pips against 52.
- when a trade goes against him, read the profit figure on his order panel and note
  the exact moment he clicks close.
- timestamp entry and exit so hold time is measured, not guessed.
- record market, session, clock time he starts and stops, trades that day.
- write every rule into research/mamba_notes.md QUOTED WORD FOR WORD.

RULE ZERO — HE IS THE AUTHORITY. Eleven rules in this project have been found
present in the code and silently doing nothing while printing entirely believable
numbers: a missing timeframe entry, wall-clock position stamps, an exit behind an
entry gate, a calendar that never advanced, a detector true 82% of the time, a
per-day cap counting only open positions, a currency conversion missing in four
places, and a rule asking for more bars than the strategy is ever handed. My tests
have been wrong about this bot more often than he has been wrong about the market.
When a number disagrees with something I watched him do, THE NUMBER IS WRONG. Build
his version, log the number in one line underneath, move on. No arguing, no
hedging, no caveats.

VERIFY EVERY RULE FIRES — this is the primary discipline, not an afterthought. For
each mechanic, count how often it triggers and how trades actually close. A rule
that never fires is not built. The tell is always that switching it on changes the
result by exactly nothing.

SAME RISK. SAME MARKETS. SAME SESSIONS. SAME HOLD TIMES. SAME STOPS. SAME TARGETS.
The only difference is speed: the bot watches every market and every level at once
and never misses an entry through being away from the screen, tired, or busy. He
says himself he cannot sit at the camera for hours. Nothing else differs.

COMMIT after every video and every gap closed. Keep research/mamba_videos.tsv
current so nothing is watched twice.

PERCENTAGES ONLY. Never dollar amounts.
```

## Practical notes to repeat when handing this over

- 36 hours of his footage exists; a thorough pass is roughly 3× that. Eleven hours
  gets through the priority-0 teaching videos and most of the trading ones. The
  tracker means the next run continues rather than restarts.
- The Mac must stay awake: `caffeinate -dimsu` in a separate Terminal window, left
  open, charger plugged in. Asleep is not off, but off is off — nothing runs.

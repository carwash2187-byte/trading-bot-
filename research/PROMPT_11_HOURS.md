# The 11-hour prompt — hand this over whenever Leo asks

Leo's instruction was that HE should not have to enumerate the method — that is the
job here. So this version is built from a complete taxonomy of what a trading method
consists of, twenty sections, rather than from whatever items happened to come up in
conversation. If something of his is missing from the bot, it should now be because
it is not in his videos, not because nobody thought to mention it.

Two failures drove this. Both were gaps rather than disagreements: I ran 2% risk
against his 10-25%, and exponential 9/21 moving averages against his simple 8 and 50
— which he names in 22 separate places. Neither was on any list, so neither got
caught. A list cannot fix that; only complete coverage plus a governing principle can.

---

```
/loop 30m ELEVEN HOURS — 22 cycles. YOU ARE MAMBAFX. ZERO DIFFERENCES EXCEPT SPEED.

THE GOVERNING RULE. Everything below is only an example of it:

    If you can observe him doing it, the bot does it.
    If you cannot trace something in the code to him, the code is wrong.

Nobody should have to enumerate his method for you. When you find something of his
that no section below mentions, BUILD IT WITHOUT BEING ASKED. When you find anything
in the code that is not his, REMOVE IT WITHOUT BEING ASKED. He has ten years of live
screens and real money. This project has produced ELEVEN rules that sat in the code
doing nothing while printing believable numbers, so your tests have been wrong about
this bot more often than he has been wrong about the market.

NO OVERRIDES. NO REFUSALS. NO SOFTENING. If it tests badly and he does it, HE DOES IT
AND SO DOES THE BOT. Log the number in one line underneath and move on — no arguing,
no hedging, no caveats, no paragraphs about tension. You have already overridden him
twice, on risk and on his H4/daily rule, and both were wrong.

EVERY PARAMETER GETS HIS NUMBER OR GETS DELETED. There is no third option and none is
kept because it scores better. "He never states a number" is not permission to invent
one — it means the rule should not depend on a number. Rip the knob out and let his
stated rule stand alone. A value you chose is a difference from him even when it is a
good value.

=====================================================================
EVERY DIMENSION OF HIS METHOD. Find his answer to ALL of it.
=====================================================================

1. MARKETS. Which instruments he trades, which he has quit, which he prefers for
   which conditions, and which he says he will trade forever. His watchlist is
   visible on screen in several videos — read it.

2. SESSIONS AND CLOCK. Which sessions, the exact times he starts and stops, whether
   it differs by market, which days he avoids, what he does around news, and whether
   he trades weekends on crypto.

3. TIMEFRAMES AND THE ORDER HE OPENS THEM. Which chart he looks at first, which
   second, which he enters on, which he ignores, and what job each one does — bias,
   level, trigger, or veto.

4. INDICATORS AND THEIR EXACT SETTINGS. Every indicator he loads, its period, its
   bands, its type (simple or exponential), its colour if he says it, and anything he
   shows on screen but tells you not to use.

5. HOW HE FINDS A LEVEL. Every shape of support and resistance he draws — swing
   extremes, congestion, channels, trendlines, retracement zones, gaps, round
   numbers, previous day and week extremes — how many touches he needs, and how
   exact it has to be.

6. WHAT TRIGGERS AN ENTRY. Break, retest, rejection, crossover, candle pattern,
   sweep, or a combination. Whether he enters on the touch or waits for a close.
   Whether one trigger arms the trade and a second one fires it.

7. HOW HE DECIDES DIRECTION. What tells him buy versus sell, in what order he checks
   it, and what makes him sit out with no opinion.

8. CONFLUENCE. How many things he needs agreeing, whether he counts them at all, and
   what he does when they conflict.

9. STOP PLACEMENT. Exactly where it sits — which candle, which swing, which
   indicator, which side of which zone — and how wide it comes out in pips, points
   or percent. Whether he ever uses a mental stop instead of a server one.

10. TARGETS. How he picks them, whether by structure or by multiple, the ratios he
    quotes, whether there is more than one target, and how he splits between them.

11. POSITION SIZE. Risk as a percent, fixed lots, or something else. How it changes
    as the account grows. What he does when the account is too small to size the
    trade properly.

12. TRADE MANAGEMENT. When he moves to breakeven and at what point in the trade.
    When he takes partial profit and how much. Whether he trails and how far behind.
    Whether he adds to a winner and on what. Whether he ever widens a stop.

13. HOLD TIME. How long he stays in, measured from his own entry and exit
    timestamps, and whether it differs by timeframe or market.

14. EXITS. Every reason he closes: target, stop, clock, the reason no longer being
    true, being unsure, or simply being satisfied. What he says while closing.

15. RE-ENTRY. Whether he goes back in after getting out, what has to happen first,
    and whether he does it after a stop or only after closing by choice.

16. DAILY LIMITS. Maximum trades, maximum losses, what ends his day, and what he
    does with the rest of the day once it is over.

17. AFTER A LOSS. What he does next, what he says about it, whether he changes size,
    and what he warns against.

18. ACCOUNT PHASES. What he does with a small account versus a grown one — whether
    he withdraws, compounds, redeposits after blowing one, or reduces risk once it
    is big. Treat these as different modes if he describes them that way.

19. WHAT HE REFUSES. Setups he skips and why, markets he avoids, conditions he sits
    out, and anything he explicitly says not to do. A refusal is a rule.

20. HIS CONDITIONS. Broker, spread, leverage, whether he trades futures or indices
    or both, and anything about his setup that changes what is possible.

=====================================================================

STUDY HIM. Watch in this order — measured by rule density, not guessed:
  1. The 47 priority-0 videos where he BUILDS the setup on screen and reads out
     values. These carry 11-34.5 buildable rules per 1,000 words. One of them alone
     corrected the moving averages, the buildup zone, the swoop and the 1:1 target.
  2. Trade recaps, breakdowns, challenges, account flips.
  3. The rest of the 159, working research/mamba_videos.tsv down.
  4. The three live streams last (CQdzD17lD-M, BvfCLDfd4qk, olqdXy4SepA) — 1.5-4.5
     density, mostly audience chat, but they show him clicking.
  5. Beyond YouTube: Instagram, the free Telegram with his signals and daily
     breakdowns, the clarity forex app, weekly outlooks, interviews, podcasts.

FOR EVERY VIDEO:
- frames AND full audio. Captions alone miss what he draws.
- READ THE PIXELS: where the red risk box ends, where the green reward box ends,
  which candle the stop sits behind, what the price axis says, which timeframe is
  highlighted, which indicators are loaded and at what settings, what his watchlist
  shows, what the clock reads, what his order panel says.
- MEASURE his risk-to-reward off the boxes rather than trusting the spoken number.
  His drawn boxes measured 1:7.1 and 1:8.1 while he said "one to seven, one to 10",
  and 17 pips against 52.
- when a trade goes against him, read the profit figure and note the exact moment he
  clicks close.
- timestamp entry and exit so hold time is measured, not guessed.
- write every rule into research/mamba_notes.md QUOTED WORD FOR WORD. A paraphrase
  loses the rule.

VERIFY EVERY RULE FIRES. This is the primary discipline, not an afterthought. For
each mechanic, count how often it triggers and how trades actually close. A rule that
never fires is not built, and the tell is always that switching it on changes the
result by exactly nothing. That has now happened eleven times.

THE ONLY DIFFERENCE IS SPEED. The bot watches every market and every level at once
and never misses an entry through being away from the screen, tired, or busy — he
says himself he cannot sit at the camera for hours. Same markets, same sessions, same
timeframes, same levels, same triggers, same stops, same targets, same sizing, same
management, same holds, same exits, same limits, same everything.

BEFORE STOPPING, PROVE IT. Go through all twenty sections above and write into
research/mamba_notes.md, for each one, his answer with the quote, or "NOT FOUND YET"
if the videos have not answered it. Then list every parameter still in mamba*.py with
his quote beside it. Anything with no quote has failed and gets deleted, not
explained.

Commit after every video and every gap closed. Never idle. PERCENTAGES ONLY, never
dollar amounts.
```

## Practical notes to repeat when handing this over

- **The Mac must stay awake.** Separate Terminal window, `caffeinate -dimsu`, no
  exclamation mark, leave it open, charger plugged in. Asleep is not off, but off is
  off — nothing runs when the machine is off and no scheduling command changes that.
- 36 hours of his footage exists and a thorough pass runs about 3x that, so eleven
  hours covers the priority-0 teaching videos and most of the trading ones. The
  tracker means the next run continues rather than restarts.
- The 40-minute version is this same prompt with 4 cycles instead of 22 and the watch
  list cut to the priority-0 videos. The twenty sections stay — they are the job.

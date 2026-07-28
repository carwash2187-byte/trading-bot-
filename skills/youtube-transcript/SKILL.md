---
name: youtube-transcript
description: Read what is said in a YouTube video by fetching its transcript. Use whenever the user shares a YouTube link or asks you to watch, check, summarise, or pull information out of a video — including trading strategy videos, tutorials, talks, and interviews.
---

# YouTube Transcript

Pulls the spoken words out of a YouTube video so they can be read, searched and
summarised. Runs locally against YouTube's own caption data — no API key, no
account, no per-request cost.

## Usage

```bash
/usr/bin/python3 -W ignore ~/.claude/skills/youtube-transcript/yt.py <url-or-id>
```

Accepts full URLs (`watch?v=`, `youtu.be`, `/shorts/`, `/live/`, `/embed/`) or a
bare 11-character video id.

| Flag | Use it when |
|---|---|
| `--timestamps` | You need to cite *when* something was said, or the user asks "where in the video…" |
| `--lang xx` | The video is not in English (`--lang es`, `--lang fr`) |
| `--langs` | Nothing came back and you want to see which caption tracks exist |

Long videos produce a lot of text. Pipe through `head -100` to check the topic
first, or `grep -i` to jump to a term, before reading the whole thing.

```bash
# what does it actually cover?
/usr/bin/python3 -W ignore ~/.claude/skills/youtube-transcript/yt.py <url> | head -60

# find every mention of a term, with times
/usr/bin/python3 -W ignore ~/.claude/skills/youtube-transcript/yt.py <url> --timestamps | grep -i "stop loss"
```

## The one real limitation

**A transcript is only what was *said*, never what was *shown*.** If a video
displays a chart, an indicator setting, a results table or numbers on screen
without the speaker reading them aloud, none of that is in the transcript.

This matters most for trading, coding and tutorial videos, where the important
detail is often on screen rather than in the narration. When a transcript is
vague exactly where the specifics should be — "so you set it to *this* value" —
that is the on-screen gap, not a broken fetch. Say so plainly rather than
guessing at the missing numbers.

## When it fails

- **"no captions at all"** — genuinely has none. Nothing to do; the audio would
  need transcribing separately.
- **"Could not read captions"** — private, deleted, age-restricted, or YouTube
  rate-limiting this IP. Retry once; if it persists, report it rather than
  silently substituting a web search for the video's content.
- **Wrong language back** — run `--langs`, then re-run with `--lang`.

Never present a summary of a video you could not actually fetch.

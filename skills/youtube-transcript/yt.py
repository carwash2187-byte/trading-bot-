#!/usr/bin/env python3
"""Fetch a YouTube transcript as plain text.

Runs entirely on this machine against YouTube's own caption data. No API key,
no third-party service, no per-request cost.

    yt.py <url-or-id> [--timestamps] [--lang es] [--langs]

A transcript is what was *said*. Anything that was only ever shown on screen --
a chart, an indicator, numbers in a corner -- is not in here. See NOTE below.
"""

import argparse
import re
import sys

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    sys.exit(
        "youtube-transcript-api is not installed. Install it with:\n"
        "  /usr/bin/python3 -m pip install --user youtube-transcript-api"
    )


# Every shape a YouTube link comes in. The bare-id branch is last so that a
# URL is never mistaken for an id.
_PATTERNS = (
    r"(?:youtube\.com|youtube-nocookie\.com)/watch\?(?:.*&)?v=([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
    r"youtube\.com/(?:embed|shorts|live|v)/([A-Za-z0-9_-]{11})",
    r"^([A-Za-z0-9_-]{11})$",
)


def video_id(text):
    text = text.strip()
    for pattern in _PATTERNS:
        found = re.search(pattern, text)
        if found:
            return found.group(1)
    raise ValueError("Could not find a video id in: %s" % text)


def pick(listing, want):
    """Choose a transcript, preferring a real one in the wanted language.

    Order matters: a human-written caption track is more accurate than an
    auto-generated one, and a machine translation is the last resort because
    it compounds two lots of error -- speech recognition, then translation.
    """
    try:
        return listing.find_manually_created_transcript([want]), "manual"
    except Exception:
        pass
    try:
        return listing.find_generated_transcript([want]), "auto-generated"
    except Exception:
        pass

    available = list(listing)
    if not available:
        raise LookupError("This video has no captions at all.")

    first = available[0]
    if first.language_code.startswith(want):
        return first, "auto-generated"
    if first.is_translatable:
        try:
            return first.translate(want), "translated from %s" % first.language
        except Exception:
            pass
    return first, "only available language (%s)" % first.language


def clock(seconds):
    seconds = int(seconds)
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def main():
    ap = argparse.ArgumentParser(description="Fetch a YouTube transcript.")
    ap.add_argument("video", help="YouTube URL or 11-character video id")
    ap.add_argument("--timestamps", action="store_true",
                    help="prefix each line with its time, for citing moments")
    ap.add_argument("--lang", default="en", help="preferred language (default: en)")
    ap.add_argument("--langs", action="store_true",
                    help="list available caption languages and exit")
    args = ap.parse_args()

    try:
        vid = video_id(args.video)
    except ValueError as exc:
        sys.exit(str(exc))

    api = YouTubeTranscriptApi()

    try:
        listing = api.list(vid)
    except Exception as exc:
        # The library's messages are long and wrapped in banners; the first
        # meaningful line is the part worth showing.
        detail = str(exc).strip().splitlines()
        sys.exit("Could not read captions for %s: %s" % (vid, detail[0] if detail else exc))

    if args.langs:
        for tr in listing:
            kind = "auto" if tr.is_generated else "manual"
            print("%-8s %-28s %s" % (tr.language_code, tr.language, kind))
        return

    try:
        transcript, how = pick(listing, args.lang)
        snippets = list(transcript.fetch())
    except LookupError as exc:
        sys.exit(str(exc))
    except Exception as exc:
        sys.exit("Could not fetch the transcript: %s" % exc)

    if not snippets:
        sys.exit("The transcript came back empty.")

    words = sum(len(s.text.split()) for s in snippets)
    minutes = int(snippets[-1].start + snippets[-1].duration) // 60
    print("# %s  (%s, ~%d min, ~%d words)" % (vid, how, minutes, words))
    print("# https://www.youtube.com/watch?v=%s" % vid)
    print()

    if args.timestamps:
        for s in snippets:
            print("[%s] %s" % (clock(s.start), s.text.replace("\n", " ")))
    else:
        # Reflow into paragraphs. Caption cues break mid-sentence, so joining
        # them and grouping by sentence-ish runs reads far better than the
        # raw two-second fragments.
        text = " ".join(s.text.replace("\n", " ") for s in snippets)
        text = re.sub(r"\s+", " ", text).strip()
        sentences = re.split(r"(?<=[.!?]) +", text)
        for i in range(0, len(sentences), 5):
            print(" ".join(sentences[i:i + 5]))
            print()


if __name__ == "__main__":
    main()

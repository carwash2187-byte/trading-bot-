# Running 24/7 with the Mac off

Every step. Copy-paste the commands; nothing here needs working out.

The bot has **zero third-party dependencies** — 23 modules, all built into Python.
No pip, no virtualenv, nothing to break on a version bump. This is why a $5 box is enough.

**One hard constraint:** this must use the **TradeLocker** broker, which speaks plain HTTPS.
MetaTrader 5 needs a Windows machine with the terminal running and will not work on a cheap
Linux server.

---

## STEP 1 — Rent the server

Any of these. Pick one, cheapest first:

| Host | Cost | Notes |
|---|---|---|
| **Hetzner** (CX22) | **~€4/mo** | Cheapest, very reliable. Falkenstein or Ashburn. |
| Vultr | $5/mo | More regions. |
| DigitalOcean | $6/mo | Easiest signup. |

When creating it:
- **Image:** Ubuntu 24.04 LTS
- **Size:** the smallest one (1 shared CPU, 1–2 GB RAM). The bot uses almost nothing.
- **Region:** pick one near your broker's servers — **London** for most FX brokers,
  **New York/Ashburn** if yours is US. This is milliseconds, not a dealbreaker.
- **SSH key:** add one if offered. Otherwise it emails you a root password.

You get an IP address. Everything below happens on that box.

---

## STEP 2 — Get in

On your Mac:

```bash
ssh root@YOUR_SERVER_IP
```

---

## STEP 3 — Make a user for the bot

Running a trading bot as root is asking for it.

```bash
adduser --disabled-password --gecos "" tradebot
apt update && apt install -y git python3
```

---

## STEP 4 — Put the code on it

```bash
su - tradebot
git clone https://github.com/carwash2187-byte/trading-bot-.git tradebot
cd tradebot
```

---

## STEP 5 — Credentials

**This is the one step that is not copy-paste — the values are yours.**

```bash
nano ~/tradebot/.env
```

Paste this, replacing the right-hand sides with your real TradeLocker details:

```
TRADELOCKER_USERNAME=your@email.com
TRADELOCKER_PASSWORD=yourpassword
TRADELOCKER_SERVER=yourserver
TRADELOCKER_ACCOUNT=youraccountnumber
TRADEBOT_START_BALANCE=150
```

The names must be **exactly** those four — the bot looks them up by name and an
unrecognised one is silently ignored, which shows up as a login failure rather than as
"you spelled it wrong". `USERNAME` is usually your email address.

Save with `Ctrl+O`, `Enter`, then `Ctrl+X`.

Then lock it so only the bot user can read it:

```bash
chmod 600 ~/tradebot/.env
```

**The `.env` is gitignored and must never be committed.** The repo is public — anything
committed to it is world-readable forever, including in the history after you delete it.

---

## STEP 6 — Install the service

```bash
exit                      # back to root
cp /home/tradebot/tradebot/deploy/tradebot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tradebot
```

That is it. It is now running, and it will start itself again if it crashes **or if the
server reboots**.

---

## STEP 7 — Check it is alive

```bash
systemctl status tradebot
```

Look for **`active (running)`** in green.

Watch it work in real time:

```bash
journalctl -u tradebot -f
```

You want lines like `staying awake: checking every 5s across NAS100,US30,GBPUSD,XAUUSD`
and then a `cycle in ...` line every five seconds. Press `Ctrl+C` to stop watching — that
stops *you* watching, not the bot.

**Close the terminal. Shut the Mac. It keeps running.**

---

## The commands you will actually use

| What | Command |
|---|---|
| Is it alive? | `systemctl status tradebot` |
| Watch it live | `journalctl -u tradebot -f` |
| What did it do today? | `journalctl -u tradebot --since today \| grep -E "order\|filled\|ERROR"` |
| Stop it | `systemctl stop tradebot` |
| Start it | `systemctl start tradebot` |
| Restart after a code change | `systemctl restart tradebot` |
| Update to newest code | `su - tradebot -c "cd tradebot && git pull"` then `systemctl restart tradebot` |

---

## STEP 8 — Going live (do this LAST, and not on day one)

It ships in **demo** mode. Leave it there until you have watched it open and close real
orders on the demo account.

When you decide to go live, two changes — deliberately two, so a typo cannot do it:

```bash
nano /etc/systemd/system/tradebot.service
```

- change `--mode demo` to `--mode live`
- add this line in the `[Service]` block:
  `Environment=TRADEBOT_ALLOW_LIVE=yes`

Then:

```bash
systemctl daemon-reload && systemctl restart tradebot
```

---

## Honest notes

- **The server never sleeps.** That is the entire point of it over the Mac.
- **It restarts itself** on crash and on reboot. If it fails five times in two minutes it
  stops on purpose, so a real fault is visible instead of thrashing quietly.
- **Cost is ~$5/month.** Nothing else to pay for — no data feed, no licences.
- **The news feed is free and needs no signup.** It is already in the service file.
- **Back up nothing.** The code is in git; the only thing on the box that matters is `.env`,
  and you typed that yourself.

# Putting the bot on a free Oracle server

Oracle Cloud's Always Free tier includes a small ARM server that runs 24/7 and
costs nothing, permanently. Once the bot lives there it does not care whether
your laptop is on, closed, out of battery, or in another country.

Two things only you can do — the signup needs your card for identity
verification (it is not charged), and the SSH key has to be downloaded in your
browser. Everything after that is one command.

---

## 1. Sign up

Go to **cloud.oracle.com** → *Start for free*.

* Use your normal email.
* Pick the **home region closest to you**. This cannot be changed later.
* It asks for a card to prove you are a person. Free tier resources stay free;
  you would have to deliberately upgrade to be charged.

Verification usually takes a few minutes, occasionally a few hours.

## 2. Create the server

In the Oracle console: **Menu → Compute → Instances → Create instance**.

* **Image**: Canonical Ubuntu 22.04
* **Shape**: click *Change shape* → **Ampere** → `VM.Standard.A1.Flex`
  → set **1 OCPU** and **6 GB memory**. This is inside the always-free
  allowance, and far more than the bot needs.
* **SSH keys**: choose *Generate a key pair for me* and **download the private
  key**. You cannot download it again later.
* Click **Create**.

When it finishes, copy the **Public IP address** from the instance page.

> **If it says "out of capacity"** — that is normal and not your fault. The
> free ARM shapes are heavily used. Either try again in a few hours, or pick
> `VM.Standard.E2.1.Micro` instead, which is also always-free and always
> available. It is a smaller machine and still comfortably enough.

## 3. Send me two things

Paste back:

1. the **public IP address**
2. the path to the **downloaded key file** (normally
   `~/Downloads/ssh-key-....key`)

I will copy the bot across, install the timers, and confirm it is trading.

---

## What happens then

The bot runs a cycle every 5 minutes, permanently:

| | |
|---|---|
| Trades | every 5 minutes |
| Daily record | appended once a day |
| Survives reboot | yes, the timers auto-start |
| Needs your laptop | no |
| Cost | nothing |

To look at it yourself later:

```bash
ssh -i /path/to/key ubuntu@YOUR_IP
cd tradebot
cat reports/daily.md          # one line a day: balance, payout days, room left
python3 doctor.py             # plain-English health check
journalctl --user -u tradebot -f   # watch it work in real time
```

## Why 5 minutes here and 20 on GitHub

GitHub Actions bills by the minute against a monthly allowance, so a 20-minute
gap was the compromise that fit inside it. A server you own has no such limit,
so the bot checks as often as its 15-minute chart can produce a new signal.

Either way the open trades are safe: the stop-loss and take-profit are held by
the broker, not by the bot, so they still protect a position while nothing at
all is running.

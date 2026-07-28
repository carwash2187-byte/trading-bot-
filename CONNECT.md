# How to connect the bot to your account

Three steps. Copy and paste each command exactly.

---

## Step 1 — make the file with your login

Open Terminal, then paste this **one block** and press enter:

```bash
cd ~/tradebot && cp .env.example .env && open -e .env
```

A text editor opens. **You only need three things** — email, password, and
server name. Fill them in so they look like this:

```
TRADELOCKER_USERNAME=your@email.com
TRADELOCKER_PASSWORD=yourpassword
TRADELOCKER_SERVER=AQUAFUNDED
TRADELOCKER_ACCOUNT=
```

No spaces around the `=`. No quotes. Then save (Cmd+S) and close.

**Leave `TRADELOCKER_ACCOUNT` empty.** The bot asks the broker which accounts
your login owns and uses the first one. Step 2 prints which it picked, and you
only need to fill this in if you have several accounts and it chose the wrong
one.

**Where to find the other three:** they are the same email, password and server
you type on the TradeLocker login screen. Nothing else to look up.

This file stays on your computer. It is already in `.gitignore`, so it is never
uploaded anywhere.

---

## Step 2 — check it can log in

```bash
cd ~/tradebot && python3 check_connection.py
```

This only logs in and reads your balance. **It cannot place a trade** — there is
no trading code in it at all. It tells you plainly whether the login worked and
whether it can see your gold prices.

If it fails, it says which of the four values is wrong.

---

## Step 3 — start the bot

Only once step 2 says everything is OK:

```bash
cd ~/tradebot && python3 run.py --broker tradelocker --mode demo \
  --strategies gold_scalper --symbols XAUUSD --verbose
```

That runs one cycle and stops, so you can watch what it does.

---

## To check on it later

```bash
cd ~/tradebot && python3 doctor.py
```

Tells you in plain English whether the bot is alive, allowed to trade, and
actually trading.

---

## A note on `--mode`

`--mode demo` is what a funded account uses — prop firm accounts report
themselves as demo even though the money is real. That is normal and expected.

`--mode live` additionally requires `TRADEBOT_ALLOW_LIVE=yes` in the
environment. That extra step exists so a real-money order can never happen by
accident, from a typo or a wrong flag. Leave it alone unless you are
deliberately trading your own money.

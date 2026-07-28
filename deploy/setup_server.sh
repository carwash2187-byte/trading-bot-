#!/usr/bin/env bash
#
# Set up the bot on a fresh Ubuntu server (Oracle Cloud Free Tier or similar).
#
# Run this ON THE SERVER, once, after copying the project across. It installs
# nothing that is not already there -- the bot deliberately has no dependencies
# beyond the Python standard library, so there is no package to break on an
# upgrade and no wheel to fail to build on ARM.
#
#   bash deploy/setup_server.sh
#
# Idempotent: safe to run again after a change. It rewrites the timers rather
# than stacking duplicates.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(id -un)"
PY="$(command -v python3)"

echo "installing tradebot from ${HERE}"
echo "  user   ${USER_NAME}"
echo "  python ${PY} ($(${PY} --version))"
echo

if [ ! -f "${HERE}/.env" ]; then
    cat <<'MSG'
No .env file found.

Create it before running this, with your four broker settings:

    nano ~/tradebot/.env

    TRADELOCKER_USERNAME=your@email.com
    TRADELOCKER_PASSWORD=yourpassword
    TRADELOCKER_SERVER=AQUA
    TRADELOCKER_ACCOUNT=

Then run this script again.
MSG
    exit 1
fi

chmod 600 "${HERE}/.env"
mkdir -p "${HERE}/logs" "${HERE}/run" "${HERE}/reports"

# systemd user units rather than cron: cron on a fresh cloud image often has no
# MAILTO and silently swallows failures, while systemd keeps the exit status and
# the last run's output where `systemctl --user status` can show them.
UNIT_DIR="${HOME}/.config/systemd/user"
mkdir -p "${UNIT_DIR}"

cat > "${UNIT_DIR}/tradebot.service" <<UNIT
[Unit]
Description=One trading cycle
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${HERE}
# The limits are spelled out rather than left at defaults so that reading this
# file tells you what the account is actually risking.
ExecStart=${PY} ${HERE}/run.py \\
  --broker tradelocker --mode demo \\
  --symbols XAUUSD --strategies gold_scalper \\
  --risk-per-trade 0.015 \\
  --daily-loss-limit 0.03 \\
  --max-drawdown-limit 0.06
UNIT

cat > "${UNIT_DIR}/tradebot.timer" <<UNIT
[Unit]
Description=Trade every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
# Without this a run that overruns its slot would stack up behind itself.
AccuracySec=30s

[Install]
WantedBy=timers.target
UNIT

cat > "${UNIT_DIR}/tradebot-report.service" <<UNIT
[Unit]
Description=Daily account record

[Service]
Type=oneshot
WorkingDirectory=${HERE}
ExecStart=${PY} ${HERE}/daily_report.py
UNIT

cat > "${UNIT_DIR}/tradebot-report.timer" <<UNIT
[Unit]
Description=Write the daily line

[Timer]
OnCalendar=*-*-* 23:17:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now tradebot.timer tradebot-report.timer

# Without this, the user's services stop the moment the SSH session ends and
# start again only at the next login -- which on a headless server is never.
if ! loginctl show-user "${USER_NAME}" 2>/dev/null | grep -q "Linger=yes"; then
    echo "enabling linger so the timers survive logout"
    sudo loginctl enable-linger "${USER_NAME}"
fi

echo
echo "checking it can reach the broker..."
cd "${HERE}"
if ${PY} check_connection.py; then
    echo
    echo "Done. The bot trades every 5 minutes."
    echo
    echo "  see the schedule    systemctl --user list-timers tradebot'*'"
    echo "  watch it work       journalctl --user -u tradebot -f"
    echo "  daily record        cat ${HERE}/reports/daily.md"
    echo "  health check        cd ${HERE} && ${PY} doctor.py"
else
    echo
    echo "Timers are installed, but the broker check failed above."
    echo "Fix that first -- until it passes, nothing will trade."
    exit 1
fi

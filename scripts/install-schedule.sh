#!/usr/bin/env bash
# Install the weekly PCH review as a macOS LaunchAgent (Mondays, 09:00).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.iridyne.pch"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$REPO/data"

if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "gui/$UID_NUM/$LABEL" || true
fi

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>$REPO/scripts/weekly.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>1</integer>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$REPO/data/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$REPO/data/launchd.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
PLIST_EOF

launchctl bootstrap "gui/$UID_NUM" "$PLIST"
launchctl enable "gui/$UID_NUM/$LABEL"

echo "installed $PLIST"
echo "next run: Monday 09:00"
echo "disable: launchctl bootout gui/$UID_NUM/$LABEL"
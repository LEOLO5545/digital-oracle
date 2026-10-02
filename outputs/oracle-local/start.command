#!/bin/zsh
cd "$(dirname "$0")"
# Close an older copy of this server (and its Codex calls) so the new version really starts.
old=$(lsof -ti tcp:8765 -sTCP:LISTEN 2>/dev/null)
if [ -n "$old" ]; then
  echo "關閉仍在運行的舊 server（PID $old）…"
  kill $old 2>/dev/null
  for i in 1 2 3 4 5; do lsof -ti tcp:8765 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done
  lsof -ti tcp:8765 -sTCP:LISTEN >/dev/null 2>&1 && kill -9 $old 2>/dev/null
fi
# Only this app's Codex calls use this exact flag combination; the Codex app is not affected.
pkill -f "codex exec --ignore-user-config --ephemeral" 2>/dev/null
exec ../../work/oracle-venv/bin/python server.py

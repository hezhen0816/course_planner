#!/usr/bin/env bash
# Deploy backend + web to the home Windows host (Tailscale node "hezhen").
#
# Usage: bash scripts/deployment/deploy_windows.sh [--skip-web]
#
# What it does:
#   1. builds web/dist pointed at the Tailscale HTTPS origin (unless --skip-web)
#   2. git pull --ff-only on the Windows checkout and installs backend deps
#   3. copies web/dist to the Windows checkout so FastAPI serves it at "/"
#   4. restarts the Course_Compass_Backend and Course_Compass_Monitor scheduled tasks
#      (Stop-Process below kills every course-compass python, the worker included)
#   5. ensures `tailscale serve` maps https://hezhen.<tailnet>.ts.net -> :8000
set -euo pipefail

SSH_HOST="${SSH_HOST:-winhome}"
WIN_REPO="${WIN_REPO:-C:/Users/hezhe/source/repos/course-compass}"
WIN_REPO_BACKSLASH="${WIN_REPO//\//\\}"
PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-https://hezhen.taile9e4a0.ts.net}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SKIP_WEB=0
[[ "${1:-}" == "--skip-web" ]] && SKIP_WEB=1

if [[ $SKIP_WEB -eq 0 ]]; then
  echo "==> Building web (VITE_BACKEND_URL=$PUBLIC_ORIGIN)"
  (cd "$ROOT" && VITE_BACKEND_URL="$PUBLIC_ORIGIN" npm --prefix web run build >/dev/null)
fi

echo "==> Updating backend checkout on $SSH_HOST"
ssh -o BatchMode=yes "$SSH_HOST" \
  "cd $WIN_REPO_BACKSLASH && git pull -q --ff-only && git log -1 --oneline && .venv\\Scripts\\python.exe -m pip install -q -r backend\\requirements.txt tzdata"

if [[ $SKIP_WEB -eq 0 ]]; then
  echo "==> Copying web/dist"
  ssh -o BatchMode=yes "$SSH_HOST" "if exist $WIN_REPO_BACKSLASH\\web\\dist rmdir /s /q $WIN_REPO_BACKSLASH\\web\\dist"
  scp -q -r "$ROOT/web/dist" "$SSH_HOST:$WIN_REPO/web/dist"
fi

echo "==> Restarting backend + monitor tasks"
# Comparison syntax (no $_) keeps this free of shell-escaping pitfalls.
ssh -o BatchMode=yes "$SSH_HOST" "powershell -NoProfile -Command \"Stop-ScheduledTask Course_Compass_Backend; Stop-ScheduledTask Course_Compass_Monitor; Get-Process python -ErrorAction SilentlyContinue | Where-Object Path -like '*course-compass*' | Stop-Process -Force; Start-Sleep 2; Start-ScheduledTask Course_Compass_Backend; Start-ScheduledTask Course_Compass_Monitor; Start-Sleep 3; Get-ScheduledTask Course_Compass_Backend, Course_Compass_Monitor | Select-Object TaskName, State | Format-Table -HideTableHeaders\""

echo "==> Ensuring tailscale serve -> :8000"
ssh -o BatchMode=yes "$SSH_HOST" "tailscale serve --bg 8000 >nul 2>&1 & tailscale serve status"

echo "==> Waiting for backend"
for _ in $(seq 1 20); do
  if curl -fsS --max-time 5 "$PUBLIC_ORIGIN/health" >/dev/null 2>&1; then
    echo "OK  $PUBLIC_ORIGIN/health"
    curl -fsS --max-time 10 "$PUBLIC_ORIGIN/" | grep -q "<title>" && echo "OK  $PUBLIC_ORIGIN/ serves the web app"
    exit 0
  fi
  sleep 3
done
echo "backend did not answer at $PUBLIC_ORIGIN/health" >&2
exit 1

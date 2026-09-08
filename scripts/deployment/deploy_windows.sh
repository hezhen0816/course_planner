#!/usr/bin/env bash
# Deploy backend + web + monitor worker to the home Windows host (Tailscale node "hezhen", ssh alias winhome).
# Same guardrails as 大金/ERP/報價系統 scripts/deploy.sh (see ~/AI協作/專案文件模板/AGENTS.md「Windows 部署」):
#
#   bash scripts/deployment/deploy_windows.sh            # tests → push → pull → 比對 HEAD → 需要時 build/重啟 → 煙霧測試
#   bash scripts/deployment/deploy_windows.sh --fast     # 跳過測試（CI 綠或剛跑過）
#   bash scripts/deployment/deploy_windows.sh --force    # 不看 diff，強制重建 web 並重啟後端與 worker
#
# Rules baked into the script instead of memory:
# - 工作樹不乾淨就不部署（未追蹤檔不擋）。
# - push 在腳本內做；pull 後遠端 HEAD 必須等於本機 HEAD。
# - 只有這次前進區間改到相關檔案才動：web/ 變了才 build + scp dist；backend/*.py 或
#   requirements 變了才重啟後端；backend/ 任何 .py 或 requirements 變了才重啟 worker
#   （worker 重啟會中斷監控幾秒並重做預先登入，純文件 commit 不該觸發）。
# - Stop-Process 只殺該任務自己的 python（看命令列），不再一刀殺掉所有 course-compass python。
# - 煙霧測試打 tailnet 入口（同學／手機實際走的那條路），不是 loopback。
set -euo pipefail

SSH_HOST="${SSH_HOST:-winhome}"
WIN_REPO="${WIN_REPO:-C:/Users/hezhe/source/repos/course-compass}"
WIN_REPO_BACKSLASH="${WIN_REPO//\//\\}"
PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-https://hezhen.taile9e4a0.ts.net}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

FAST=0; FORCE=0
for arg in "$@"; do
  case "$arg" in
    --fast) FAST=1 ;;
    --force) FORCE=1 ;;
    --skip-web) echo "（--skip-web 已由 diff 判斷取代；web/ 沒變就自動跳過）" ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

win() { ssh -o BatchMode=yes "$SSH_HOST" "$@"; }
win_ps() { ssh -o BatchMode=yes "$SSH_HOST" "powershell -NoProfile -Command \"$1\""; }
restart_task() {  # $1 task name, $2 substring that identifies its python command line
  win_ps "Stop-ScheduledTask $1; Get-CimInstance Win32_Process | Where-Object { \$_.Name -eq 'python.exe' -and \$_.CommandLine -like '*course-compass*' -and \$_.CommandLine -like '*$2*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }; Start-Sleep 2; Start-ScheduledTask $1; Start-Sleep 2; (Get-ScheduledTask $1).State"
}

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "✗ 工作樹有未提交變更，先 commit 再部署："; git status --short; exit 1
fi

if [[ $FAST -eq 0 ]]; then
  echo "==> 後端測試"; npm run backend:test --silent >/dev/null
  echo "==> 前端 lint"; npm run web:lint --silent >/dev/null
else
  echo "==> 跳過測試（--fast）"
fi

echo "==> push"
git push -q origin HEAD:main
LOCAL_HEAD="$(git rev-parse HEAD)"

echo "==> $SSH_HOST pull"
BEFORE="$(win "cd $WIN_REPO_BACKSLASH && git rev-parse HEAD" | tr -d '\r')"
AFTER="$(win "cd $WIN_REPO_BACKSLASH && git pull -q --ff-only && git rev-parse HEAD" | tr -d '\r')"
[[ "$AFTER" == "$LOCAL_HEAD" ]] || { echo "✗ 那台 HEAD $AFTER ≠ 本機 $LOCAL_HEAD"; exit 1; }
echo "    $BEFORE → $AFTER"

CHANGED="$(git diff --name-only "$BEFORE" "$AFTER" 2>/dev/null || true)"
changed() { [[ $FORCE -eq 1 ]] || grep -qE "$1" <<<"$CHANGED"; }

if changed '^web/'; then
  echo "==> build web (VITE_BACKEND_URL=$PUBLIC_ORIGIN)"
  (VITE_BACKEND_URL="$PUBLIC_ORIGIN" npm --prefix web run build --silent >/dev/null)
  echo "==> copy web/dist"
  win "if exist $WIN_REPO_BACKSLASH\\web\\dist rmdir /s /q $WIN_REPO_BACKSLASH\\web\\dist"
  scp -q -r "$ROOT/web/dist" "$SSH_HOST:$WIN_REPO/web/dist"
else
  echo "==> web/ 沒變，跳過 build 與 dist 同步"
fi

if changed '^backend/requirements\.txt$'; then
  echo "==> requirements 有變，pip install"
  win "cd $WIN_REPO_BACKSLASH && .venv\\Scripts\\python.exe -m pip install -q -r backend\\requirements.txt tzdata"
fi

NEED_BACKEND=0; NEED_WORKER=0
# 後端不載入 backend/monitor/*；共用模組都在 backend/ 根層或 api/、typed_planner/
if changed '^backend/(requirements\.txt$|[^/]+\.py$|(api|typed_planner)/.*\.py$)'; then NEED_BACKEND=1; fi
if changed '^backend/.*\.py$|^backend/requirements\.txt$'; then NEED_WORKER=1; fi
if changed '^scripts/deployment/run_backend\.bat$'; then NEED_BACKEND=1; fi
if changed '^scripts/deployment/run_monitor\.bat$'; then NEED_WORKER=1; fi

if [[ $NEED_BACKEND -eq 1 ]]; then
  echo "==> 後端有變更，重啟 Course_Compass_Backend"; restart_task Course_Compass_Backend "uvicorn"
else
  echo "==> 後端沒變，不重啟"
fi
if [[ $NEED_WORKER -eq 1 ]]; then
  echo "==> worker 有變更，重啟 Course_Compass_Monitor"; restart_task Course_Compass_Monitor "backend.monitor.worker"
else
  echo "==> worker 沒變，不重啟"
fi

echo "==> ensure tailscale serve -> :8000"
win "tailscale serve --bg 8000 >nul 2>&1 & tailscale serve status" | tr -d '\r' | sed 's/^/    /'

echo "==> 煙霧測試（tailnet 入口）"
for _ in $(seq 1 20); do
  if curl -fsS --max-time 5 "$PUBLIC_ORIGIN/health" >/dev/null 2>&1; then
    echo "OK  $PUBLIC_ORIGIN/health"
    curl -fsS --max-time 10 "$PUBLIC_ORIGIN/" | grep -q "<title>" && echo "OK  $PUBLIC_ORIGIN/ serves the web app"
    if [[ $NEED_WORKER -eq 1 ]]; then
      STATE="$(win_ps "(Get-ScheduledTask Course_Compass_Monitor).State" | tr -d '\r')"
      echo "OK  Course_Compass_Monitor: $STATE"
      [[ "$STATE" == "Running" ]] || { echo "✗ worker 沒在跑"; exit 1; }
    fi
    echo "✓ 部署完成：$AFTER"
    exit 0
  fi
  sleep 3
done
echo "✗ backend did not answer at $PUBLIC_ORIGIN/health" >&2
exit 1

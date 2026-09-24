#!/bin/bash
# Prepares a Claude Code on the web session: Python + Node deps and the
# Chromium build that the pinned Playwright version expects.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Python (uv downloads Python 3.12 itself if the image only has 3.11).
uv sync --locked --all-groups

# Frontend workspace.
pnpm install --frozen-lockfile

# The image ships an older Playwright Chromium in /opt/pw-browsers; install the
# build matching apps/miniapp's @playwright/test into a separate cache instead.
PW_PATH="$HOME/.cache/ms-playwright-burmaldoza"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD= PLAYWRIGHT_BROWSERS_PATH="$PW_PATH" \
  pnpm --dir apps/miniapp exec playwright install chromium

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PLAYWRIGHT_BROWSERS_PATH=\"$PW_PATH\"" >> "$CLAUDE_ENV_FILE"
fi

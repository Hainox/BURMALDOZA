# CLAUDE.md

@AGENTS.md

## Только для Claude Code

- Рабочие ветки — `claude/<задача>`; PR открывать черновиком.
- В облачной сессии зависимости и Chromium для Playwright ставит `.claude/hooks/session-start.sh`
  (он же выставляет `PLAYWRIGHT_BROWSERS_PATH`). Docker недоступен — интеграционные тесты с PostgreSQL
  проверяются в CI.
- Последний аудит: [docs/Code-Audit-2026-09-23.md](./docs/Code-Audit-2026-09-23.md).

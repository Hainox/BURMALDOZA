# Blackjack и Poker — итог реализации

Поручение владельца: отдельный Blackjack до 3 игроков, Poker до 6,
с сохранением solo/bot. Все действия, включая публикацию, разрешены24.10.2026.
Код восстановлен после автоматической очистки; результаты ниже получены заново.

## Реализовано

- Blackjack: создание/вход по коду,3 места,ready/start,общая колода и дилер,
  Hit/Stand/Double,20 секунд и Stand по сроку,повторные раунды,late join/leave.
- Poker: очередь6/60 секунд,старт2–6,одиночный поиск без списания,all-in/reopening,
  side pots/refunds/odd chips,20 секунд и check/fold,личная история.
- Durable actor-bound UUID replay,атомарный ledger,сохранение deadline и private
  state; общие HTTP/WS-проекции не раскрывают чужие карты и балансы.
- Потеря ответа и перезагрузка сохраняют pending UUID; отмена/выход повторяются
  даже при403 на snapshot; временный503 не теряет комнату.
- GFL/RGG оформление,Supericons,320/390/1440px,reduced motion и пауза анимаций.

## Подтверждённые проверки

- Полный pytest:413 passed,3 warnings,без skipped; PostgreSQL16.2 + Redis6.2.14.
- Ruff и git diff --check:passed.
- Frontend check:0 errors/0 warnings; Vitest77 passed; production build passed.
- Полный Playwright:77/77 passed на80d12d6,включая solo/slot/sound/reconnect.
- Последние две правки (quiet/terminal board copy) проверяются отдельным новым
  quiet-тестом и повтором всех multiplayer браузерных сценариев.
- CI основной версии181765a:success (PostgreSQL16/Redis7,Docker,E2E,Monte Carlo).

PR: https://github.com/Hainox/BURMALDOZA/pull/121
Ветка:codex/multiplayer-recovery. Main и production не изменены.
Ручная Telegram-приёмка настоящими аккаунтами и server deploy не выполнялись.
Scratch Chromium153.0.8010.0 отличается патчем от ожидаемого .12; Redis6.2 локально
отличается от CI7. Новых runtime dependencies и миграций нет.

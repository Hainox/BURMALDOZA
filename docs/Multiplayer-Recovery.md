# Восстановление multiplayer — 24.10.2026

Поручение: завершить Blackjack table до3 и Poker до6 с сохранением solo/bot.
Публикация разрешена владельцем24.10.2026. После автоматической очистки рабочая
копия восстановлена; исторические тесты22.10 не являются проверкой новых байтов.

## Текущий подтверждённый checkpoint

- Blackjack domain/service:20 passed.
- Poker domain/service:62 passed.
- Старый Hold'em server/timer:29 passed,2 предупреждения зависимостей.
- Ruff по восстановленным серверным файлам — passed.
- PostgreSQL/Redis среда восстанавливается; её тесты пока не засчитаны.
- Интерфейсы и браузерная приёмка восстанавливаются; не завершены.

Ветки: локальная codex/multiplayer-completion; удалённый checkpoint
codex/multiplayer-recovery. Новые версии blackjack-gfl-table-1 и holdem-six-1
выбираются явно. Общий EventBus не должен содержать private cards/балансы.
Неизвестная версия не декодируется старым движком. Новые stakes/payouts проходят
через WalletService. Новых runtime dependencies и миграций нет.

Остаток: общий HTTP/WS regression, PostgreSQL гонки, frontend check/test/build/E2E,
исправления замечаний ревью и финальные документы. Не считать checkpoint релизом.

# Build Specification — Бурмалдоза, skeleton v0.1

**Статус:** технический skeleton собран; финальные тематические ассеты, лимиты и публичный запуск требуют отдельной приёмки.

## Goal

Запустить Telegram-бота и Mini App «Бурмалдоза» для сообщества Memendoza: серверно подтверждаемая виртуальная экономика и три игровые комнаты с ясной, живой анимацией.

## Approved rooms

| Комната | Правила | Статус foundation |
| --- | --- | --- |
| 3×7 Slot | Три барабана, семь видимых рядов, paylines и integer payout | domain + Monte Carlo + Mini App skeleton |
| Blackjack GFL | Hit / Stand / Double, dealer resolution, integer-safe payout | domain + Monte Carlo + Mini App skeleton |
| Heads-up Hold’em / RGG Poker | Два места, один pot, Fold / Check / Call / Raise | domain + equity simulation + Mini App skeleton |

Итог раунда рассчитывает сервер. Клиент отправляет intent, получает подтверждённый snapshot/event и лишь затем проигрывает соответствующую фазу движения.

### Slot v2 — обязательный motion-контур

- `SlotOutcome`/room event содержит финальную сетку, paylines, payout, новый баланс и состояние Free Spins.
- Клиент проигрывает полную вертикальную прокрутку барабанов с разгоном, инерционным торможением и staged stop: левый → центральный → правый.
- Payline, payout и изменение баланса показываются только после подтверждённой остановки; клиент не генерирует RNG и не исправляет серверный результат.
- Первый каркас поддерживает пять Free Spins с отдельным серверным исходом каждого вращения.
- Бонусная мини-игра временно остаётся заглушкой и вынесена в отдельную переделку после приёмки Slot v2.

## Economy v0.1

- Рабочее название валюты: **Jokergem**, код `JOKERGEM`; название остаётся сменным без миграции балансов.
- Хранятся целые единицы, не деньги и не финансовые значения.
- Стартовая выдача: `1 000 JOKERGEM` один раз.
- Ежедневная выдача: `250 JOKERGEM` раз в 24 часа.
- Relief-грант: `300 JOKERGEM`, если баланс ниже `50`, не чаще одного раза в 72 часа.
- Нет покупки, вывода, обмена, призов, Stars и P2P-переводов.
- Каждая мутация имеет `X-Request-ID`/idempotency key и append-only ledger.

Стартовые числа — техническая baseline-конфигурация для закрытого теста, а не обещание игрокам и не решение о монетизации.

## Scope

- Привязка бота к одному выбранному чату комментариев.
- `/start`, `/casino`, `/balance`, `/top`, `/help` и кнопка входа в Mini App.
- Проверка сырого Telegram `initData` на API; `initDataUnsafe` не является trust boundary.
- Профиль, баланс, журнал операций, комнаты, snapshot/event и восстановление после reconnect.
- Роли администраторов, лимиты, аудит и редкие анонсы только отдельным разрешённым действием.
- PostgreSQL как источник истины, Redis для locks/presence/pub-sub, SvelteKit для интерфейса и motion.

## Out of scope

- Реальные деньги, криптовалюта, вывод, обмен, платные шансы и продажа игровой валюты.
- Stars до отдельного BuildSpec, юридической проверки, `/paysupport`, возвратов и журнала платежей.
- Сбор полной истории чатов, RAG, анализ токсичности и фоновые массовые рассылки.
- Мультичатность до стабилизации одного сообщества.
- Финальные персонажи и тематические ассеты до прохождения domain/API/room тестов и приёмки визуального направления.

## Acceptance criteria

- Пользователь открывает Mini App из Telegram и получает серверно-проверенный профиль.
- Баланс не вычисляется и не хранится как источник истины в браузере.
- Повтор tap/retry и две конкурентные ставки не создают второе списание или вторую выплату.
- Старый `state_version` отклоняется; reconnect читает durable snapshot и не дублирует action.
- Slot, Blackjack и Hold’em проходят доменные переходы, integer payout/tie-split проверки и воспроизводимые симуляции.
- UI сохраняет legal actions, объяснение результата, focus states, safe-area padding и readable state при reduced motion.
- Slot UI показывает полную прокрутку барабанов, подтверждённую сетку, payout highlight и Free Spins без подмены outcome на клиенте.
- Бот не пишет в чат без действия пользователя или явно включённого admin announcement.
- Секреты не попадают в source, fixtures, logs, Docker image layers или тестовые ответы.
- CI выполняет Python lint/tests, PostgreSQL integration tests, Mini App check/test/build и три Monte Carlo reports.

## Remaining product decisions before public launch

1. Утвердить финальный RTP/лимиты для каждой тематической версии поверх skeleton rulesets.
2. Утвердить финальные тематические ассеты, персонажей, звук и правила публичного шаринга.
3. Зафиксировать владельцев, модераторов, целевой чат, FAQ и поддержку.
4. Провести ручную приёмку iOS, Android и Telegram Desktop на staging.
5. Провести юридический/security review перед любым платным контуром.

Визуальный motion-слой передаётся в Command Code только по [зафиксированному workflow](../docs/Command-Code-Workflow.md), с моделью, effort, ограничением файлов и тестами.

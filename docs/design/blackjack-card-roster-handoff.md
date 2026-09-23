# Blackjack GFL — CCode handoff после выбора колоды

**Статус:** подготовка; roster A/B — варианты для владельца, не финальный канон.
**Модель:** `meta/muse-spark-1.3-contributor`, effort `high`.
**Задача:** [#6 — Blackjack room UI and motion](https://github.com/Hainox/BURMALDOZA/issues/6).
**Матрица:** [blackjack-card-roster.html](./blackjack-card-roster.html).

## Зафиксированное направление

- Girls' Frontline 1, старт сюжета 2062; форпост Griffin & Kryuger в секторе 09.
- Персонажи на всех номиналах, в том числе 2–10. Портретное досье рекомендуется; чиби — вариант.
- Масть и ранг стандартные: A=1/11, 2–10=номинал, J/Q/K=10.
- Владелец выбирает один из двух полных составов по 52 разных персонажа или подтверждает смесь.
- Рубашка: A) досье S09; B) радиосетка; C) план Safe House.
- Звук: тихие генератор/вентиляция/радио; редкие дальние радиосигналы; либо только звуки действий.
- Арты не скопированы. Не hotlink'ать IOP Wiki и не добавлять изображения/SFX без проверки прав каждого файла.

## Изоляция CCode

Сначала дождаться слияния PR #5 в main, затем создать ветку `ccode/blackjack-ui` от свежей main. Использовать `meta/muse-spark-1.3-contributor`, effort `high`, после выбора владельцем состава.

Разрешённые файлы:
- `apps/miniapp/src/lib/rooms/BlackjackRoom.svelte`
- `apps/miniapp/src/routes/+page.svelte` — только snapshot/types Blackjack
- `apps/miniapp/tests/e2e/blackjack-room.spec.ts`
- `dev/ProjectLog.md`
- `ChangeLog.md` — только для изменения, видимого игроку

Не менять domain, RNG, ledger, миграции, API-контракты, правила, зависимости, Slot и Hold'em. Не раскрывать hole card/total дилера до settlement. Дилерский образ косметический, стабилен в партии/reconnect.

## Приёмка

- Все 52 карты имеют выбранного персонажа/placeholder; угловые индексы читаемы на узком экране.
- Portrait/chibi и reduced-motion не скрывают смысл состояния или действие.
- Арт, рубашка и звук не влияют на серверную механику.
- Скрытая карта и её вклад в total недоступны клиенту до server reveal.
- Дилерский Doll случаен только как аватар и не задаёт порядок колоды.
- Playwright проверяет deal, разрешённые действия, snapshot/reconnect и отсутствие утечки hole card; ручная приёмка Telegram iOS/Android/Desktop отдельно.
- Передать CCode выбранный roster и ссылку на коммит; не поручать реализацию по неутверждённому черновику.

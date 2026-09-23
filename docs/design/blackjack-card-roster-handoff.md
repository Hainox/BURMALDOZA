# Blackjack GFL — CCode handoff после выбора колоды

**Статус:** направление владельцем выбрано; handoff готов к реализации после мержа art/design checkpoint в main.
**Модель:** meta/muse-spark-1.3-contributor, effort high.
**Задача:** [#6 — Blackjack room UI and motion](https://github.com/Hainox/BURMALDOZA/issues/6).
**Матрица состава:** [blackjack-card-roster.html](./blackjack-card-roster.html).

## Зафиксировано владельцем

- Колода **A**: 52 разных персонажа из blackjack-card-roster.html.
- Лица карт: **портретное досье** на всех рангах A, 2–10, J, Q, K.
- Рубашка: **A — досье S09**.
- Комната: G&K forward base / Sector 09, ранний сюжет GFL 1, 2062 год; не использовать полицейское оцепление или WWII-тематику из будущей темы слота Rainbow Six Siege.
- Звук пока задан как концепция: тихий генератор/вентиляция, редкие радиопомехи, короткий звук слайда карты и сдержанный сигнал только после подтверждённого результата. В репозитории нет лицензированных игровых SFX; не добавлять фиктивное воспроизведение.
- Против бота показывать случайную T-Doll из состава только как косметический аватар партии; выбор не влияет на карты, RNG, действия, выплату или баланс и восстанавливается после reconnect.
- Имена и роли персонажей — визуальное оформление. Blackjack-значения неизменны: A=1/11, 2–10 по номиналу, J/Q/K=10.

## Арт и права

- Оригинальные концепты комнаты и рубашки: assets/design/blackjack-gfl/deck-a/generated/.
- 52 портрета IOP Wiki сохранены только локально в рабочем каталоге assets/design/blackjack-gfl/deck-a/portraits/; их нет в публичном Git. Права на распространение не подтверждены.
- **Не копировать IOP-портреты в Mini App и не делать hotlink.** Использовать доступные оригинальные концепты и явно обозначенные portrait slots/fallback до получения лицензированных/разрешённых файлов.
- Локальное полноцветное превью preview.local.html использует изображения, которые намеренно не входят в публичный checkpoint.

## CCode-задача

Сначала дождаться мержа design checkpoint в main, затем создать ветку ccode/blackjack-ui от свежего main. Модель meta/muse-spark-1.3-contributor, effort high.

Разрешённые файлы:
- apps/miniapp/src/lib/rooms/BlackjackRoom.svelte
- apps/miniapp/src/routes/+page.svelte — только snapshot/types Blackjack
- apps/miniapp/tests/e2e/blackjack-room.spec.ts — новый сценарий
- dev/ProjectLog.md
- ChangeLog.md — только если есть изменение, видимое игроку

Визуально придерживаться портретного шаблона досье, крупных контрастных угловых индексов, рубашки A и палитры проекта. Использовать исходные серверные snapshot/legal actions. Закрытая карта — единая рубашка без имени/портрета/ранга/масти/total до серверного reveal.

Не менять domain, RNG, ledger, миграции, API-контракты, правила, зависимости, Slot или Hold’em.

## Приёмка

- Все 52 позиции Deck A представлены без дублей; для неподтверждённого арта отображается явный portrait placeholder, не случайная картинка.
- На мобильной ширине читаются ранг, масть, имя и важное действие; safe area, focus и reduced-motion сохранены.
- Случайная T-Doll дилера меняется только между партиями, сохраняется при reconnect и остаётся косметической.
- Hole card и total дилера скрыты до серверного завершения; исход, выигрыш и баланс берутся только из подтверждённых данных.
- Playwright проверяет deal, legal actions, hidden card, settlement, reconnect и reduced-motion.
- Передать отдельным PR; в отчёте перечислить файлы, команды/результаты и недостающие разрешённые арты.

Проверки:
- pnpm miniapp:check
- pnpm miniapp:test
- pnpm miniapp:build
- pnpm --dir apps/miniapp exec playwright test tests/e2e/blackjack-room.spec.ts

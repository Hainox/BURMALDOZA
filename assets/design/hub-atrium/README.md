# Хаб «Ночной атриум» — #90

Владелец выбрал вариант 2 из трёх концептов Product Design 14.10.2026.
`selected.png` — выбранный визуальный источник; `implementation-390.png` — проверенная
реализация в Chromium, 390×844 CSS px, density 1, reduced motion, DEMO.

Растровые ассеты `apps/miniapp/static/hub/*.webp` созданы ImageGen по выбранному
направлению. Три взрослых встречающих маскота основаны на существующем
`assets/readme/hero-subject-fullbody.jpg`. Отдельные порталы: тактический Slot Siege,
бирюзовый Blackjack GFL, красный Hold’em «Камуро-тё».

Дополнительное поручение владельца: главным персонажем портала Blackjack сделать
M4 SOPMOD / SOPPO по двум предоставленным портретам. Источник исходной публикации
портретов не предоставлен; это не заявляется как официальный artwork.
Исходные портреты не публикуются в репозитории. Персонаж относится к Girls’ Frontline.

Размеры, байты, SHA256 и происхождение runtime-файлов: `apps/miniapp/static/hub/sources.json`.
Иконки — Tabler через Supericons, MIT; полный текст лицензии лежит рядом с SVG.
Комнаты и игровые правила в этот редизайн не входят.

## Продолжение работы

## Порталы героев — #99

Ветка `codex/hub-portal-heroes`: временные коллажи заменены цельными иллюстрациями
ImageGen. Тачанка — в Maska-шлеме и тактическом снаряжении; Кирю — седой, с бородкой
и тёмной рубашкой из Infinite Wealth. Референсы личности использованы только при
генерации, исходный портрет Кирю не опубликован. © Ubisoft / © SEGA RGG;
некоммерческий фан-интерфейс, общая лицензия не заявляется.

Runtime: `slot-portal.webp` и `holdem-portal.webp`, 640×1280, каждый ≤200 000 байт.
Точные размеры, происхождение и SHA256 — в `static/hub/sources.json`.
Сравнение Chromium DEMO, reduced motion, 390×844:
`portals-before-390.png` / `portals-after-390.png`.

Промпты: цельная кинематографическая иллюстрация внутри золотой арки с пропорциями
портала SOPPO, отражающий чёрный пол, герой крупно и с общим освещением сцены.
Slot — Maska «Д 045», золотой свет и дым, надпись «SLOT SIEGE» в нижней трети,
тактический ящик на переднем плане. Hold'em — лицо Кирю Y8 по референсу, красный
свет, фонарь, сакура, фишки и стакан, надписи «Hold'em» и «КАМУРО-ТЁ» с «Ё».
Использован встроенный ImageGen; WebP сжат Pillow без изменения композиции.

Ветка `codex/hub-atrium-redesign`, issue #90. Установить зависимости
`pnpm install --frozen-lockfile`, запуск `pnpm --dir apps/miniapp dev --host 127.0.0.1 --port 4179 --strictPort`.
Композиция хаба — `apps/miniapp/src/lib/components/hub/HubLobby.svelte`, интеграция —
`apps/miniapp/src/routes/+page.svelte`, проверки — `apps/miniapp/tests/e2e/hub.spec.ts`.

Проверено: check — 0 ошибок/предупреждений; unit — 44 passed; build через E2E — success;
полный E2E — 51 passed; дополнительный запуск 5 hub-тестов — passed, сохранён screenshot.
В mocked LIVE тестах служебные непромоканные endpoint могут возвращать 404;
это не проверка настоящего сервера или Telegram WebView.

Осталось: независимое review и CI на опубликованном head; проверка владельцем внутри
Telegram на Android/iOS (safe areas, вход/возврат, фон/пауза, реальные бонусы).
PR #92 (`claude/bet-picker`) появился параллельно: при интеграции сверить +page.svelte,
не заменять его игровые обработчики. PR #87 профиля Hold’em — отдельная задача.
Merge меняет публичный Pages; серверный deploy и merge этим редизайном не выполнены.

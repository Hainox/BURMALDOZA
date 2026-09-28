# Бурмалдоза — GitHub Pages

Сайт проекта публикуется на GitHub Pages по адресу <https://hainox.github.io/BURMALDOZA/>.
GitHub Pages раздаёт статические файлы: он не запускает Python API или Telegram-бота.

## Основная Mini App

Workflow **Deploy Pages demo** собирает Mini App из `main` с базовым путём `/BURMALDOZA` и добавляет интерактивный превью Deck A/B. Он запускается при изменениях Mini App, графики Deck A/B, корневых `package.json` и `pnpm-lock.yaml`, а также самого workflow. Его можно запустить вручную из Actions, выбрав `main`.

Основной build получает `PUBLIC_API_BASE_URL` из GitHub Actions variable с таким именем. Возможность live-запросов зависит также от Telegram WebView и валидного `initData`.

## Slot v2 preview

Workflow **Deploy Pages Slot v2 preview** добавляет отдельную статическую сборку по адресу <https://hainox.github.io/BURMALDOZA/slot-v2/>. Он не запускается при push или открытии PR. После слияния workflow в `main` владелец может запустить его вручную:

1. Сначала разрешить блокер [issue #37](https://github.com/Hainox/BURMALDOZA/issues/37) и убедиться, что выбранный `preview_ref` содержит принятые честные DEMO-подписи. Пока блокер не решён, preview не публиковать.
2. В репозитории открыть **Actions → Deploy Pages Slot v2 preview → Run workflow**. Для запуска workflow выбрать ветку `main`.
3. В поле `preview_ref` указать `main` после слияния исправления из #37. Если владелец отдельно одобрил другой ref, указать его только после проверки, что там есть это исправление.
4. Нажать **Run workflow** и дождаться успешных jobs `build` и `deploy`.
5. Открыть <https://hainox.github.io/BURMALDOZA/slot-v2/> на телефоне и проверить загрузку страницы и барабанов.

Workflow всегда собирает корень и Deck A/B из актуального `main`, а Slot v2 — из указанного `preview_ref`. Для Slot v2 сборки `PUBLIC_API_BASE_URL` пуст: этот путь остаётся DEMO и не обращается к live API. Выбранный ref задаёт код Mini App и зависимости, поэтому запускайте только доверенную и проверенную ветку/ревизию.

## Откат Slot v2 preview

Чтобы убрать `/slot-v2/` и оставить опубликованную версию только с основным сайтом, вручную запустить **Deploy Pages demo** из `main`. Он опубликует корневую сборку без каталога preview. Это меняет только Pages; сервер и его данные не затрагиваются.

## Проверка основной страницы

- Открыть <https://hainox.github.io/BURMALDOZA/> на телефоне и desktop.
- Проверить переходы Mini App и превью Deck A/B по адресу `/BURMALDOZA/design/blackjack-deck-a/`.
- Для Slot v2 проверять отдельно адрес с суффиксом `/slot-v2/` и отсутствие запросов к live API.
- Убедиться, что адреса CSS, JavaScript и других статических ресурсов загружаются без 404.

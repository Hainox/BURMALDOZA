# Git и PR

## Перед коммитом

Пройди чеклист из `docs/agents/security.md` по застейдженным изменениям.

## Коммиты

`<type>(<scope>)?: <description>` — как в истории: тип `feat`, `fix`, `docs`, `test`, `ci`, `chore`, `refactor`, `perf` (встречаются и `deploy`, `design`), scope по затронутой части (`fix(miniapp):`, `test(blackjack):`). Конфиг commitlint, если появится, важнее.

## Pull request'ы

Заголовок — в стиле коммитов: при squash-merge он им станет. Описание пиши по всей ветке (`git log <base>..HEAD`), а не по последнему коммиту, и заканчивай планом проверки: что ты запустил и что ревьюеру проверить руками.

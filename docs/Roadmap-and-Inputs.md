# Бурмалдоза — roadmap и inputs от владельца

Технический foundation уже собран. Следующий порядок: ручная приёмка → тематические ассеты → закрытая beta → public launch.

## Уже зафиксировано

- Первый community-контур: Memendoza и один linked discussion chat.
- Mini App — основной игровой интерфейс; бот — вход и короткие подтверждённые команды.
- Три skeleton rooms: 3×7 Slot, Blackjack GFL, heads-up Hold’em / RGG Poker.
- Provisional currency: Jokergem (`JOKERGEM`), integer-only и без денежной ценности.
- Starter baseline: welcome `1000`, daily `250`, relief `300` below `50` once per 72h.
- Нет покупки, вывода, обмена, Stars или P2P до отдельного решения.

## Нужно до staging

1. Свежий `BOT_TOKEN` от @BotFather — только через секретный канал, не в чат и не в репозиторий.
2. Точный linked discussion chat, Telegram ID владельцев и список модераторов.
3. HTTPS-домен для Mini App/API и схема dev/staging/prod.
4. Support contact, FAQ и правила публичности выигрышей.
5. Подтверждение, что community и права на новый логотип/персонажей можно использовать.

## Нужно до thematic pass

1. Финальные RTP, min/max bet и лимиты частоты по каждой комнате.
2. 3–6 референсов «да» и «нет» для комнат, персонажей и мемных ситуаций.
3. Утверждённые исходники логотипа, avatar crops и форматы для Mini App/канала.
4. Решение по звуку, haptics и motion intensity с reduced-motion fallback.
5. Тексты правил и result explanations на русском.

## Нужно до public launch

1. Manual QA на iOS, Android и Telegram Desktop.
2. Backup/restore drill, rate limits, incident response и план отката.
3. Privacy/data retention policy для профиля и leaderboard.
4. Owner sign-off по ruleset, экономике, ролям и всем публичным copy.

## Только если появится Stars

Stars требуют отдельного BuildSpec: цифровой товар/поддержка, `pre_checkout_query`, `successful_payment`, возвраты, `/paysupport`, отдельный ledger и legal/platform review. Stars не должны покупать игровой шанс, JOKERGEM или право вывода.

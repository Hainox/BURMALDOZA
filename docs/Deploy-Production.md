# Деплой в продакшен — runbook

Как поднять Бурмалдозу на сервере по решениям из [`docs/Launch-Checkpoint.md`](./Launch-Checkpoint.md).
Стек описан в [`docker-compose.prod.yml`](../docker-compose.prod.yml).

Репозиторий публичный. В этом документе нет и не должно появиться: IP сервера, паролей, токенов,
ключей и путей на ПК владельца. Всё это хранится у владельца (менеджер паролей) и в `.env` на сервере.
Команды ниже выполняются на сервере по SSH под пользователем `deploy`, если не сказано иное.
Деплой делает локальный агент на ПК владельца или сам владелец. Облачные агенты на сервер не заходят.

## 1. Как устроено

```text
Интернет ──80/443──▶ caddy ──/api/*, /health*──▶ api (1 процесс, 1 worker) ──▶ postgres, redis
                        └────── всё остальное ────▶ miniapp (статика nginx)
bot ──HTTP по внутренней сети bot_api──▶ api; bot ──edge/наружу──▶ Telegram Bot API
```

- Наружу открыт только Caddy: 80 и 443 (TCP, плюс UDP для HTTP/3). У PostgreSQL, Redis, API и Mini App
  нет `ports`. Порты, опубликованные Docker, обходят ufw (R1), поэтому закрытость держится именно на этом.
- PostgreSQL и Redis — во внутренней сети `backend` без выхода в интернет; до них достаёт только `api`.
- Бот обращается к API напрямую по `API_BASE_URL=http://api:8000` через отдельную сеть `bot_api`
  с `internal: true`, доступную только сервисам `bot` и `api`. Конфигурация бота в production
  разрешает HTTP только для этого точного адреса; `MINIAPP_URL` остаётся HTTPS. Сеть `edge` у бота
  нужна только для исходящих запросов к Telegram Bot API.
- Caddy возвращает 404 на публичном сайте для `/api/v1/internal` и всех его подмаршрутов до общего
  проксирования `/api/*`. Внутренние маршруты API дополнительно требуют отдельный `INTERNAL_API_TOKEN`.
- API — ровно один процесс: явный `--workers 1`, одна реплика, без `WEB_CONCURRENCY` (R5). Пока
  `EventBus` живёт в памяти процесса, второй worker или реплика потеряет live-события.
- Mini App получает адрес API **при сборке образа** (build-arg `PUBLIC_API_BASE_URL`, R3). По умолчанию
  `https://burmaldoza.ru`. Пустое значение собрало бы DEMO-клиент.
- Сертификаты Let's Encrypt Caddy получает сам. `www.burmaldoza.ru`, `burmaldoza.online` и
  `www.burmaldoza.online` постоянно перенаправляются на `https://burmaldoza.ru`.
- Конфигурация Caddy встроена в compose-файл (`configs.content`), поэтому нужен Docker Compose **2.23.1+**.
- API читает правила слота из `/app/tests/fixtures/slot_skeleton.json`. Production Compose
  монтирует этот отслеживаемый Git-файл read-only через `configs`; он должен присутствовать в
  checkout выбранного SHA. Сам API-образ его не содержит: без mount создание комнаты даёт 500.

## 2. Что должно быть готово до начала (владелец)

- [ ] Сервер переустановлен: Ubuntu 22.04 **без** шаблона Portainer, вход по ключу `ed25519` владельца.
- [ ] DNS: A-записи `@` и `www` для `burmaldoza.ru` и `burmaldoza.online` указывают на сервер и уже
      разошлись (`nslookup burmaldoza.ru` с ПК владельца показывает IP сервера). Без этого Caddy не получит
      сертификат, а частые неудачные попытки упираются в лимиты Let's Encrypt.
- [ ] `burmaldoza.ru` подтверждён в Рег.ру.
- [ ] Новый бот создан в @BotFather, токен YUVI отозван. Новый токен вводится **только** в `.env` на сервере.
- [ ] Для резервных копий создана пара ключей `age` (раздел 7): закрытый ключ — только у владельца.
- [ ] Решено, куда уходят копии вне сервера (раздел 7.3).

## 3. Подготовка сервера (однократно)

Выполняются под root сразу после переустановки. Вход по паролю отключается **только после** того,
как вход по ключу под `deploy` проверен в отдельном окне.

```bash
set -euo pipefail
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys && chmod 600 /home/deploy/.ssh/authorized_keys
passwd deploy            # пароль для sudo — в менеджер паролей владельца

apt update && apt -y upgrade
apt -y install ufw fail2ban unattended-upgrades age git ca-certificates curl openssl python3
dpkg-reconfigure -plow unattended-upgrades

ufw default deny incoming && ufw default allow outgoing
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
ufw enable

fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Docker Engine и плагин Compose ставятся из официального apt-репозитория Docker. Snap и Ubuntu-пакет
`docker.io` не подходят: в них нет современного Compose v2. Нужен Compose **2.23.1+** (раздел 1),
поэтому версия проверяется сразу после установки.

```bash
set -euo pipefail
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt update
apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker deploy
docker compose version
```

Если версия ниже 2.23.1 — остановиться и обновить плагин Compose: `configs.content` из
`docker-compose.prod.yml` на старых версиях не разбирается. Членство в группе `docker` применяется
к новой сессии `deploy`, поэтому после `usermod` выйти из SSH-сессии и войти заново, прежде чем
запускать `docker` без `sudo`. Официальные инструкции: <https://docs.docker.com/engine/install/ubuntu/>.
Docker вставляет правила iptables в обход `ufw`, поэтому закрытость держится не на `ufw`, а на том,
что в `docker-compose.prod.yml` порты публикует только Caddy (R1).

После проверки входа `ssh deploy@<сервер>` по ключу: в `/etc/ssh/sshd_config` задать
`PasswordAuthentication no` и `PermitRootLogin prohibit-password`, затем `systemctl reload ssh`.

**Portainer** (решение от 24.09.2026) — только на локальном интерфейсе, наружу не публикуется:

```bash
set -euo pipefail
docker volume create portainer_data
docker run -d --name portainer --restart=unless-stopped -p 127.0.0.1:9443:9443 \
  -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:lts
```

Вход — через туннель с ПК владельца: `ssh -L 9443:127.0.0.1:9443 deploy@<сервер>`, затем
`https://localhost:9443`. Пароль администратора задаётся сразу после установки.

## 4. Код и `.env`

```bash
set -euo pipefail
sudo install -d -o deploy -g deploy /srv/burmaldoza
git clone https://github.com/Hainox/BURMALDOZA.git /srv/burmaldoza
cd /srv/burmaldoza
git checkout <SHA из main, одобренный владельцем>
```

`.env` создаётся на сервере и никогда не коммитится, не копируется в чат и не печатается в лог.
Секреты генерируются прямо на сервере, их значения на экран не выводятся. Это процедура **первой
установки**: существующий `.env` не перезаписывать; выключить shell tracing (`set +x`). Для пароля
PostgreSQL используется hex, чтобы символы `@`, `:`, `/` не ломали DSN. Дальнейшая ротация пароля
требует отдельного согласованного изменения роли в PostgreSQL и конфигурации API.

```bash
set -euo pipefail
cd /srv/burmaldoza
(
set -eu
umask 077
set -o noclobber
cat > .env <<'EOF'
POSTGRES_DB=burmaldoza
POSTGRES_USER=burmaldoza
MINIAPP_URL=https://burmaldoza.ru
PUBLIC_API_BASE_URL=https://burmaldoza.ru
EOF
set +o noclobber
printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 32)" >> .env
printf 'INTERNAL_API_TOKEN=%s\n' "$(openssl rand -hex 32)" >> .env
# Токен из @BotFather вводит владелец; ввод не отображается и не попадает в историю shell:
read -rsp 'BOT_TOKEN: ' t && printf 'BOT_TOKEN=%s\n' "$t" >> .env; unset t; echo
chmod 600 .env
cut -d= -f1 .env         # проверка: только имена переменных, без значений
)
```

| Переменная | Откуда | Примечание |
|---|---|---|
| `POSTGRES_PASSWORD` | `openssl rand -hex 32` | Меняется только вместе с данными базы. |
| `BOT_TOKEN` | @BotFather | Нужен и API (проверка `initData`), и боту. |
| `INTERNAL_API_TOKEN` | `openssl rand -hex 32` | Одно значение для API и бота, **не равно** `BOT_TOKEN` (R6). |
| `MINIAPP_URL` | `https://burmaldoza.ru` | CORS и кнопка Mini App в боте. |
| `PUBLIC_API_BASE_URL` | `https://burmaldoza.ru` | Build-arg Mini App; при пустом значении подставится он же. |

`ENVIRONMENT=production` задан в compose-файле. `WEB_CONCURRENCY`, `API_PORT`, `MINIAPP_PORT` и
`DATABASE_URL` из `.env.example` в продакшене не используются; `WEB_CONCURRENCY` не задавать вовсе.
Все обязательные значения стоят в compose с `:?`: если чего-то нет, `compose config` и `up` остановятся
до запуска контейнеров.

## 5. Предварительные проверки перед каждым запуском

```bash
set -euo pipefail
cd /srv/burmaldoza
for name in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD BOT_TOKEN INTERNAL_API_TOKEN MINIAPP_URL PUBLIC_API_BASE_URL; do
  if printenv "$name" >/dev/null; then
    printf 'Exported %s overrides the server .env; unset it and rerun this block.\n' "$name" >&2
    exit 1
  fi
done
C=(docker compose -f /srv/burmaldoza/docker-compose.prod.yml --env-file /srv/burmaldoza/.env)
git status --short && git log -1 --format='%h %s'      # чистое дерево, ожидаемый SHA
docker compose version                                 # 2.23.1+
"${C[@]}" config --quiet                                # обязательные значения заданы
"${C[@]}" config --format json | python3 -c '
import json, sys
s = json.load(sys.stdin)["services"]
assert {k for k,v in s.items() if v.get("ports")} == {"caddy"}
assert {(str(p["published"]), p["protocol"]) for p in s["caddy"]["ports"]} == {("80","tcp"),("443","tcp"),("443","udp")}
assert "--workers 1" in " ".join(s["api"]["command"])
assert "WEB_CONCURRENCY" not in s["api"]["environment"]
assert s["miniapp"]["build"]["args"]["PUBLIC_API_BASE_URL"] == "https://burmaldoza.ru"
assert s["bot"]["environment"]["API_BASE_URL"] == "http://api:8000"
assert set(s["bot"]["networks"]) == {"edge", "bot_api"}
assert set(s["api"]["networks"]) == {"backend", "edge", "bot_api"}
assert s["networks"]["bot_api"]["internal"] is True
assert s["api"]["environment"]["MINIAPP_URL"] == s["bot"]["environment"]["MINIAPP_URL"] == "https://burmaldoza.ru"
token = s["api"]["environment"]["INTERNAL_API_TOKEN"]
assert len(token) >= 64 and token.isascii() and token.isalnum()
assert token == s["bot"]["environment"]["INTERNAL_API_TOKEN"] != s["api"]["environment"]["BOT_TOKEN"]
print("Production configuration OK")'
getent hosts burmaldoza.ru www.burmaldoza.ru burmaldoza.online www.burmaldoza.online
sudo ufw status verbose                                 # 22, 80, 443/tcp, 443/udp
df -h / && free -h
```

Во всех блоках нужен Bash; при любой ошибке остановиться и исправить её до следующей команды. Compose
даёт экспортированным переменным оболочки приоритет перед `--env-file`; проверка выше останавливается,
если в текущей сессии есть такие переменные, и выводит только их имена. Раздел 6 выполняйте в той же
SSH/Bash-сессии, чтобы сохранился массив `C`.
Вывод `config --format json` выше идёт прямо в валидатор, который печатает только результат.
Не добавлять `tee`, shell tracing и вывод исходного JSON: в нём находятся секреты.

## 6. Запуск и проверка

```bash
set -euo pipefail
cd /srv/burmaldoza
for name in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD BOT_TOKEN INTERNAL_API_TOKEN MINIAPP_URL PUBLIC_API_BASE_URL; do
  if printenv "$name" >/dev/null; then
    printf 'Exported %s overrides the server .env; unset it and rerun this block.\n' "$name" >&2
    exit 1
  fi
done
C=(docker compose -f /srv/burmaldoza/docker-compose.prod.yml --env-file /srv/burmaldoza/.env)
"${C[@]}" build --pull api bot miniapp
"${C[@]}" pull postgres redis caddy
"${C[@]}" up -d --no-build --pull never --wait --wait-timeout 180 postgres redis api miniapp caddy
curl -fsS https://burmaldoza.ru/health/ready
"${C[@]}" run --rm --no-deps -T --entrypoint python bot - <<'PY'
import asyncio
from app.main import load_config
from app.api_client import BotApiClient
async def check():
    c = load_config()
    client = BotApiClient(c.api_base_url, c.internal_api_token)
    try:
        await client.get_top()
        print("Bot internal API auth OK")
    finally:
        await client.close()
asyncio.run(check())
PY
"${C[@]}" up -d --no-build --pull never bot
"${C[@]}" ps
```

API при старте сам выполняет `alembic upgrade head`. Четыре сервиса с healthcheck должны быть
`healthy`; Caddy и bot — `running` (у них нет healthcheck). `--wait` не доказывает готовность TLS
и Telegram polling: поэтому бот запускается после успешного HTTPS/API probe. В `PORTS` могут быть
видны внутренние `EXPOSE` Dockerfile; только Caddy должен иметь привязки хоста вида `0.0.0.0:…->…`.
При ошибке проверить локально отфильтрованные логи нужного сервиса; не публиковать сырые логи бота,
в которых HTTP-клиент может включить Telegram URL с токеном. Срок выпуска сертификата не гарантирован.

Проверки после запуска (условия технического запуска из чекпоинта, раздел 6):

| Проверка | Как | Ожидается |
|---|---|---|
| Готовность API | `curl -fsS https://burmaldoza.ru/health/ready` | HTTP 200 |
| Сертификат и редиректы | `curl -fsSL -o /dev/null -w '%{url_effective}\n' http://burmaldoza.online` и аналогично для `https://www.burmaldoza.ru` и `https://www.burmaldoza.online` | Итоговый URL — `https://burmaldoza.ru/`; HTTP сначала может перейти на HTTPS того же alias |
| Live, а не DEMO | Открыть Mini App из бота | Индикатор подключения **не** показывает `DEMO` |
| Первый вход | `/start` → Mini App новым аккаунтом | Баланс 1 000 JOKERGEM, спин слота проходит |
| Внутренние API-маршруты закрыты снаружи | С внешнего ПК выполнить `curl -i https://burmaldoza.ru/api/v1/internal/bot/top` и `curl -i https://burmaldoza.ru/api/v1/internal/bot/users/1/wallet` | Оба ответа — HTTP 404, без содержимого внутренних обработчиков |
| Внутренние порты закрыты | С ПК владельца: `Test-NetConnection <сервер> -Port 5432` (и 6379, 8000, 8080) | `TcpTestSucceeded: False` |
| Слушающие порты на сервере | `sudo ss -tlnp` | Наружу только 22, 80, 443 и `127.0.0.1:9443` |
| Бот ходит во внутренний API | `/balance` и `/top` в боте | Баланс и рейтинг отображаются; иначе проверить `bot_api`, `INTERNAL_API_TOKEN` и логи без публикации сырых Telegram URL |
| Один API-процесс | `"${C[@]}" top api` и `"${C[@]}" ps -q api` | Один процесс `uvicorn`, без дочерних worker-ов, один контейнер |

## 7. Резервное копирование

Ночная копия PostgreSQL шифруется открытым ключом `age`. На сервере лежит только открытый ключ, поэтому
архив нельзя расшифровать одним лишь ключом шифрования на сервере. Доступ к работающему серверу
всё равно даёт доступ к исходной базе. Закрытый ключ хранится у владельца; без него копии бесполезны.
Redis не является источником игровых данных, в копию не входит. Секреты `.env` владелец отдельно
сохраняет в менеджере паролей; дамп PostgreSQL их не заменяет.

### 7.1. Ключи (владелец, на своём ПК, однократно)

```bash
set -euo pipefail
age-keygen -o burmaldoza-backup.key     # печатает открытый ключ вида age1...
```

`burmaldoza-backup.key` — закрытый ключ: сохранить в менеджер паролей владельца и в офлайн-копию,
в репозиторий, чат и на сервер не класть. Открытый ключ `age1…` секретом не является.

### 7.2. Ночной дамп (сервер)

```bash
set -euo pipefail
sudo install -d -m 700 -o deploy -g deploy /var/backups/burmaldoza /etc/burmaldoza
echo 'age1...открытый ключ владельца...' | sudo tee /etc/burmaldoza/backup-recipient.txt >/dev/null
sudo tee /usr/local/bin/burmaldoza-backup >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
umask 077
for name in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD BOT_TOKEN INTERNAL_API_TOKEN MINIAPP_URL PUBLIC_API_BASE_URL; do
  if printenv "$name" >/dev/null; then
    printf 'Exported %s overrides the server .env; unset it and rerun the backup.\n' "$name" >&2
    exit 1
  fi
done
exec 9>/var/backups/burmaldoza/.backup.lock
flock -n 9 || exit 1
cd /srv/burmaldoza
out="/var/backups/burmaldoza/burmaldoza-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
test ! -e "$out"
trap 'rm -f -- "$out.tmp"' EXIT
docker compose -f docker-compose.prod.yml --env-file .env exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  | age -R /etc/burmaldoza/backup-recipient.txt > "$out.tmp"
test -s "$out.tmp"
mv "$out.tmp" "$out"
printf '%s\n' "$out"
EOF
sudo chmod 755 /usr/local/bin/burmaldoza-backup
/usr/local/bin/burmaldoza-backup && ls -lh /var/backups/burmaldoza      # первый запуск вручную
if ! crontab -l 2>/dev/null | grep -Fqx '30 3 * * * /usr/local/bin/burmaldoza-backup'; then
  ( crontab -l 2>/dev/null || true; printf '%s\n' '30 3 * * * /usr/local/bin/burmaldoza-backup' ) | crontab -
fi
```

Проверить `command -v age flock` перед установкой задания. Cron запускает `deploy`, а не root.
Добавить строку cron один раз и проверить `crontab -l`. Владелец контролирует код завершения,
возраст последнего архива и доставку вне сервера; без этого наличие cron не означает наличие копии.
Хранить минимум 14 дней; удалять старые архивы только после подтверждения внешних копий. Скрипт
не удаляет историю автоматически. Права файлов — 600, каталога — 700.

### 7.3. Копия вне сервера — решение владельца

Нужна минимум одна копия вне сервера. Варианты: владелец раз в сутки забирает файлы на свой ПК
(`scp deploy@<сервер>:/var/backups/burmaldoza/*.age <своя папка>`, задача планировщика Windows)
или сервер отправляет их в объектное хранилище (`rclone` с отдельным ключом только на запись).
Файлы уже зашифрованы, поэтому хранилищу доверять не нужно. Выбранный вариант записать в
`dev/ProjectLog.md` без адресов и ключей.

## 8. Проверка восстановления (обязательно перед техническим запуском)

Восстановление проверяется на **отдельной** базе. Боевая база не трогается. Расшифровка идёт на ПК
владельца, и закрытый ключ не попадает на сервер: поток уходит по SSH сразу в `pg_restore`.

```bash
set -euo pipefail
# на сервере: пустая база для проверки
for name in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD BOT_TOKEN INTERNAL_API_TOKEN MINIAPP_URL PUBLIC_API_BASE_URL; do
  if printenv "$name" >/dev/null; then
    printf 'Exported %s overrides the server .env; unset it and rerun this block.\n' "$name" >&2
    exit 1
  fi
done
C=(docker compose -f /srv/burmaldoza/docker-compose.prod.yml --env-file /srv/burmaldoza/.env)
restore_db="burmaldoza_restore_$(date -u +%Y%m%d%H%M%S)"
"${C[@]}" exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$restore_db"
printf '%s\n' "$restore_db"     # перенести это несекретное имя в следующий блок на ПК
```

```bash
set -euo pipefail
# на ПК владельца, в Git Bash (Windows PowerShell 5 портит двоичный поток в конвейере):
# расшифровать свежую копию и восстановить в проверочную базу
read -rp 'Имя новой проверочной базы с сервера: ' restore_db
[[ "$restore_db" =~ ^burmaldoza_restore_[0-9]{14}$ ]] || exit 1
age -d -i burmaldoza-backup.key burmaldoza-<дата>.dump.age | ssh deploy@<сервер> \
  "docker compose -f /srv/burmaldoza/docker-compose.prod.yml --env-file /srv/burmaldoza/.env exec -T postgres \
   sh -c 'pg_restore -U \"\$POSTGRES_USER\" -d \"$restore_db\" --no-owner --exit-on-error --single-transaction'"
```

Оставьте серверную SSH/Bash-сессию из первого блока открытой, пока выполняете блок на ПК: следующий
серверный блок использует сохранённые в ней `C` и `restore_db`.

```bash
set -euo pipefail
# на сервере: агрегаты и согласованность кошельков с ledger; записей игроков не печатаем
[[ "$restore_db" =~ ^burmaldoza_restore_[0-9]{14}$ ]] || exit 1
"${C[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1' sh "$restore_db" <<'SQL'
SELECT (SELECT count(*) FROM users) AS users,
       (SELECT count(*) FROM wallets) AS wallets,
       (SELECT count(*) FROM wallet_operations) AS operations,
       (SELECT count(*) FROM ledger_entries) AS entries,
       (SELECT coalesce(sum(balance),0) FROM wallets) AS balance,
       (SELECT coalesce(sum(amount_delta),0) FROM ledger_entries) AS ledger_delta;
SELECT count(*) AS inconsistent_wallets FROM wallets w
LEFT JOIN (SELECT wallet_id, sum(amount_delta) AS total FROM ledger_entries GROUP BY wallet_id) l
ON w.user_id = l.wallet_id WHERE w.balance <> coalesce(l.total,0);
SELECT version_num FROM alembic_version;
SQL
```

Нужен успешный exit code всего конвейера, `inconsistent_wallets=0` и ожидаемая версия миграции.
При проверке копии перед обновлением сравнить агрегаты с исходной базой, пока писатели остановлены.
Для ночной копии текущая боевая база могла измениться: сравнивать её текущие числа на равенство нельзя.
Каждая проверка получает новое имя с датой; `createdb` с существующим именем должен завершиться
ошибкой. Не подставлять в этот сценарий имя боевой базы. Проверочную базу можно удалить отдельно после
проверки результата. Записать дату, SHA кода, файл копии, ревизию и результат в `dev/ProjectLog.md`.

## 9. Обновление и откат

Обновление — только на SHA из `main`, одобренный владельцем, после зелёного CI на этом SHA.
До обновления сохранить **реально запущенные образы всех шести сервисов**. Повторная сборка старого
SHA не является точным откатом: базовые image tags могут уже указывать на другие версии.

Выполняйте первый и следующие серверные блоки раздела 9 в одной SSH/Bash-сессии: последующие команды
используют переменные `C` и `release_dir`, созданные в первом блоке. При разрыве сессии остановитесь и
повторно пройдите нужный шаг по фактическому состоянию; не запускайте следующий блок вслепую.

```bash
set -euo pipefail
cd /srv/burmaldoza
for name in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD BOT_TOKEN INTERNAL_API_TOKEN MINIAPP_URL PUBLIC_API_BASE_URL; do
  if printenv "$name" >/dev/null; then
    printf 'Exported %s overrides the server .env; unset it and rerun this block.\n' "$name" >&2
    exit 1
  fi
done
C=(docker compose -f /srv/burmaldoza/docker-compose.prod.yml --env-file /srv/burmaldoza/.env)
umask 077
release="$(git rev-parse HEAD)-$(date -u +%Y%m%dT%H%M%SZ)"
release_dir="/srv/burmaldoza-releases/$release"
sudo install -d -m 700 -o deploy -g deploy "$release_dir"
git rev-parse HEAD > "$release_dir/source.sha"
printf 'services:\n' > "$release_dir/images.yml"
images=()
for service in postgres redis api bot miniapp caddy; do
  container=$("${C[@]}" ps -q "$service")
  test -n "$container" || break
  id=$(docker inspect --format '{{.Image}}' "$container")
  source="$id"
  if ! docker image inspect "$id" >/dev/null 2>&1; then
    # containerd store: .Image is a config digest, while tags address manifests/indices.
    source=$(docker inspect --format '{{.Config.Image}}' "$container")
    expected=$(docker inspect --format '{{.ImageManifestDescriptor.digest}}' "$container")
    platform=$(docker inspect --format '{{.ImageManifestDescriptor.platform.os}}/{{.ImageManifestDescriptor.platform.architecture}}' "$container")
    actual=$(docker image inspect --platform "$platform" --format '{{.Id}}' "$source")
    test -n "$expected" && test "$actual" = "$expected" || break
  fi
  tag="burmaldoza-rollback/$service:$release"
  docker tag "$source" "$tag" || break
  images+=("$tag")
  printf '  %s:\n    image: %s\n' "$service" "$tag" >> "$release_dir/images.yml"
done
test "${#images[@]}" -eq 6                              # продолжать только при успехе
docker image save -o "$release_dir/images.tar" "${images[@]}"
sha256sum "$release_dir/images.tar" > "$release_dir/images.tar.sha256"
```

Проверить свободное место для образов, дампа и второй базы. `images.yml` содержит только имена
образов, `.env` туда не копируется. Не удалять сохранённые образы и архив до приёмки нового выпуска.
Если сохранение любого из шести образов не прошло, остановить обновление. Для containerd image store
сверяется digest платформы текущего контейнера; если tag уже заменён другой сборкой, команда
останавливается. Сохранять образы нужно до новой сборки/pull. На старом image store используется ID.
Проверить `git status`, выполнить `git fetch origin`, затем перейти на одобренный SHA и собрать
новые `api bot miniapp`. Образы PostgreSQL/Redis/Caddy не обновлять вместе с кодом приложения;
их обновление и совместимость данных проверяются отдельно. При ошибке сборки вернуть прежний SHA:
запущенные контейнеры ещё не менялись.

Окно обслуживания: остановить **оба** источника запросов до финальной копии. С этого момента
игры недоступны; не запускать API новой версии до успешного резервного копирования.

```bash
set -euo pipefail
"${C[@]}" stop bot api
backup_file=$(/usr/local/bin/burmaldoza-backup)
test -s "$backup_file"
printf '%s\n' "$backup_file" > "$release_dir/backup.path"
# Проверить восстановление именно этого архива по разделу 8, сравнить агрегаты при остановленных API/bot.
# После успеха: обновить только приложение, без пересоздания DB/Redis/Caddy.
"${C[@]}" up -d --no-deps --no-build --pull never --wait --wait-timeout 180 api miniapp
curl -fsS https://burmaldoza.ru/health/ready
# Выполнить bot internal API probe из раздела 6, затем:
"${C[@]}" up -d --no-deps --no-build --pull never bot
```

Если меняется конфигурация самого Caddy — применить её отдельным шагом после review и проверки
сертификата. При ротации `INTERNAL_API_TOKEN` API и бот останавливаются вместе, получают одно новое
значение, затем выполняется HTTPS/API probe и запускается бот. `compose up` сам по себе не является
атомарным обновлением двух сервисов. После запуска выполнить всю таблицу раздела 6.

**Откат кода** (схема совместима). Выбрать сохранённый `release_dir`; проверить SHA/архив, загрузить
образы, вернуть старый source SHA. Использовать override с сохранёнными образами и запретить сборку
и pull. Не запускать старые инфраструктурные образы поверх данных от новой major-версии PostgreSQL.

```bash
set -euo pipefail
sha256sum -c "$release_dir/images.tar.sha256"
docker image load -i "$release_dir/images.tar"
"${C[@]}" stop bot api
git checkout --detach "$(cat "$release_dir/source.sha")"
R=("${C[@]}" -f "$release_dir/images.yml")
"${R[@]}" config --quiet
"${R[@]}" up -d --no-deps --no-build --pull never --wait --wait-timeout 180 api miniapp
curl -fsS https://burmaldoza.ru/health/ready
# HTTPS/API probe из раздела 6, используя R вместо C, затем:
"${R[@]}" up -d --no-deps --no-build --pull never bot
```

**Откат после несовместимой миграции.** Сначала остановить bot/API. Владелец выбирает копию и
подтверждает, что действия после её создания не попадут в восстановленную базу. Сохранить также
зашифрованный дамп текущего состояния для разбора. Полностью восстановить предрелизную копию в
новую базу `$restore_db` по разделу 8, проверить суммы, количество записей и старую ревизию схемы.
При любой ошибке не переключать базу. Исходная база не удаляется: после успешной проверки имена
меняются местами, а исходная остаётся под именем `burmaldoza_failed_<дата>`.

```bash
set -euo pipefail
failed_db="burmaldoza_failed_$(date -u +%Y%m%dT%H%M%SZ)"
[[ "$restore_db" =~ ^burmaldoza_restore_[0-9]{14}$ ]] || exit 1
"${C[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -v live="$POSTGRES_DB" -v failed="$1" -v restored="$2"' sh "$failed_db" "$restore_db" <<'SQL'
ALTER DATABASE :"live" ALLOW_CONNECTIONS false;
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'live';
ALTER DATABASE :"live" RENAME TO :"failed";
ALTER DATABASE :"restored" RENAME TO :"live";
SQL
# Только после успеха: откат кода на сохранённые образы по блоку выше, затем проверки раздела 6.
```

Переименование не является одной транзакцией. Если любой шаг завершился ошибкой, оставьте API/bot
остановленными и **сначала** проверьте имена баз через `psql -lqt`; не запускайте весь блок повторно.
Если исходная база всё ещё называется `$POSTGRES_DB`, но подключения запрещены, разрешите их снова:

```bash
"${C[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -v live="$POSTGRES_DB"' <<'SQL'
ALTER DATABASE :"live" ALLOW_CONNECTIONS true;
SQL
```

Если исходная база уже переименована в `$failed_db`, а `$POSTGRES_DB` отсутствует, верните её под
боевое имя и включите подключения:

```bash
"${C[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -v live="$POSTGRES_DB" -v failed="$1"' sh "$failed_db" <<'SQL'
ALTER DATABASE :"failed" RENAME TO :"live";
ALTER DATABASE :"live" ALLOW_CONNECTIONS true;
SQL
```

Выполните только тот сценарий, который соответствует результату проверки имён. После восстановления
повторите проверки раздела 6; база `burmaldoza_failed_<дата>` сохраняется до отдельного решения владельца.
`alembic downgrade` допускается только после проверки downgrade конкретной миграции в review.


## 10. Чего не делать

- Не добавлять `ports` сервисам кроме `caddy`, не масштабировать `api` (`--scale`, `replicas`),
  не задавать `WEB_CONCURRENCY` и `--workers` больше 1 (R5).
- Не публиковать Portainer (`9443`) наружу — только `127.0.0.1` и SSH-туннель.
- Не запускать `docker compose config` без `--quiet` в логируемой сессии: он печатает секреты.
- Не коммитить `.env`, дампы и ключи `age`; не вставлять токены в чаты, issue и PR.
- Не собирать Mini App с пустым `PUBLIC_API_BASE_URL`: получится DEMO-клиент.
- Не удалять тома `postgres_data` и `caddy_data` (`down -v`): первый — это все данные игроков, второй — сертификаты.

## 11. Чек-лист владельца

1. Раздел 2: сервер, DNS, подтверждение `.ru`, новый BotFather-токен, ключи `age`, решение по копиям вне сервера.
2. Раздел 4: ввести `BOT_TOKEN` на сервере; `POSTGRES_PASSWORD` и `INTERNAL_API_TOKEN` сгенерированы там же.
3. Раздел 6: пройти таблицу проверок, включая `/start` → 1 000 JOKERGEM → спин.
4. Раздел 8: проверить восстановление копии на отдельной базе и записать дату в `dev/ProjectLog.md`.
5. @BotFather: Mini App URL = `https://burmaldoza.ru`.

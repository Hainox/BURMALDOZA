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
bot ──▶ api (внутренняя сеть) и Telegram Bot API (наружу)
```

- Наружу открыт только Caddy: 80 и 443 (TCP, плюс UDP для HTTP/3). У PostgreSQL, Redis, API и Mini App
  нет `ports`. Порты, опубликованные Docker, обходят ufw (R1), поэтому закрытость держится именно на этом.
- PostgreSQL и Redis — во внутренней сети `backend` без выхода в интернет; до них достают только `api` и `bot`.
- API — ровно один процесс: явный `--workers 1`, одна реплика, без `WEB_CONCURRENCY` (R5). Пока
  `EventBus` живёт в памяти процесса, второй worker или реплика потеряет live-события.
- Mini App получает адрес API **при сборке образа** (build-arg `PUBLIC_API_BASE_URL`, R3). По умолчанию
  `https://burmaldoza.ru`. Пустое значение собрало бы DEMO-клиент.
- Сертификаты Let's Encrypt Caddy получает сам. `www.burmaldoza.ru`, `burmaldoza.online` и
  `www.burmaldoza.online` постоянно перенаправляются на `https://burmaldoza.ru`.
- Конфигурация Caddy встроена в compose-файл (`configs.content`), поэтому нужен Docker Compose **2.23.1+**.

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
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys && chmod 600 /home/deploy/.ssh/authorized_keys
passwd deploy            # пароль для sudo — в менеджер паролей владельца

apt update && apt -y upgrade
apt -y install ufw fail2ban unattended-upgrades age git ca-certificates curl
dpkg-reconfigure -plow unattended-upgrades

ufw default deny incoming && ufw default allow outgoing
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
ufw enable

fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Docker Engine и плагин Compose ставятся из официального репозитория Docker
(<https://docs.docker.com/engine/install/ubuntu/>), затем `usermod -aG docker deploy`.
Проверка: `docker compose version` — не ниже 2.23.1.

После проверки входа `ssh deploy@<сервер>` по ключу: в `/etc/ssh/sshd_config` задать
`PasswordAuthentication no` и `PermitRootLogin prohibit-password`, затем `systemctl reload ssh`.

**Portainer** (решение от 24.09.2026) — только на локальном интерфейсе, наружу не публикуется:

```bash
docker volume create portainer_data
docker run -d --name portainer --restart=unless-stopped -p 127.0.0.1:9443:9443 \
  -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:lts
```

Вход — через туннель с ПК владельца: `ssh -L 9443:127.0.0.1:9443 deploy@<сервер>`, затем
`https://localhost:9443`. Пароль администратора задаётся сразу после установки.

## 4. Код и `.env`

```bash
sudo install -d -o deploy -g deploy /srv/burmaldoza
git clone https://github.com/Hainox/BURMALDOZA.git /srv/burmaldoza
cd /srv/burmaldoza
git checkout <SHA из main, одобренный владельцем>
```

`.env` создаётся на сервере и никогда не коммитится, не копируется в чат и не печатается в лог.
Секреты генерируются прямо на сервере, их значения на экран не выводятся:

```bash
cd /srv/burmaldoza
umask 077
cat > .env <<'EOF'
POSTGRES_DB=burmaldoza
POSTGRES_USER=burmaldoza
MINIAPP_URL=https://burmaldoza.ru
PUBLIC_API_BASE_URL=https://burmaldoza.ru
EOF
printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 32)" >> .env
printf 'INTERNAL_API_TOKEN=%s\n' "$(openssl rand -hex 32)" >> .env
# Токен из @BotFather вводит владелец; ввод не отображается и не попадает в историю shell:
read -rsp 'BOT_TOKEN: ' t && printf 'BOT_TOKEN=%s\n' "$t" >> .env; unset t; echo
chmod 600 .env
cut -d= -f1 .env         # проверка: только имена переменных, без значений
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
cd /srv/burmaldoza
C="docker compose -f docker-compose.prod.yml --env-file .env"
git status --short && git log -1 --format='%h %s'      # чистое дерево, ожидаемый SHA
docker compose version                                 # 2.23.1+
$C config --quiet && echo "compose OK"                  # падает, если нет обязательного секрета
$C config --format json | grep -c WEB_CONCURRENCY       # должно быть 0
$C config | grep -E '^\s+published:'                   # только 80, 443, 443 (caddy)
getent hosts burmaldoza.ru www.burmaldoza.ru burmaldoza.online www.burmaldoza.online
sudo ufw status verbose                                 # 22, 80, 443/tcp, 443/udp
df -h / && free -h
```

`config` без `--quiet` печатает значения секретов — не запускать его в логируемой сессии и не
копировать вывод в чат.

## 6. Запуск и проверка

```bash
$C build --pull
$C up -d
$C ps                     # все сервисы healthy; колонка PORTS заполнена только у caddy
$C logs --tail=100 caddy  # «certificate obtained successfully» для четырёх имён
$C logs --tail=100 api    # миграции Alembic применились, Uvicorn стартовал с одним процессом
```

API при старте сам выполняет `alembic upgrade head`. Первый выпуск сертификатов занимает до минуты.

Проверки после запуска (условия технического запуска из чекпоинта, раздел 6):

| Проверка | Как | Ожидается |
|---|---|---|
| Готовность API | `curl -fsS https://burmaldoza.ru/health/ready` | HTTP 200 |
| Сертификат и редиректы | `curl -sI http://burmaldoza.online` и `https://www.burmaldoza.ru` | 301/308 на `https://burmaldoza.ru/…` |
| Live, а не DEMO | Открыть Mini App из бота | Индикатор подключения **не** показывает `DEMO` |
| Первый вход | `/start` → Mini App новым аккаунтом | Баланс 1 000 JOKERGEM, спин слота проходит |
| Внутренние порты закрыты | С ПК владельца: `Test-NetConnection <сервер> -Port 5432` (и 6379, 8000, 8080) | `TcpTestSucceeded: False` |
| Слушающие порты на сервере | `sudo ss -tlnp` | Наружу только 22, 80, 443 и `127.0.0.1:9443` |
| Бот ходит в API | `/balance` в боте | Баланс, а не ошибка (иначе проверить `INTERNAL_API_TOKEN`) |
| Один API-процесс | `$C top api` | Один процесс `uvicorn`, без дочерних worker-ов |

## 7. Резервное копирование

Ночная копия PostgreSQL шифруется открытым ключом `age`. На сервере лежит только открытый ключ, поэтому
даже с сервером копию не прочитать. Закрытый ключ хранится у владельца; без него копии бесполезны —
это урок YUVI. Redis хранит только временные блокировки и присутствие, в копию не входит.

### 7.1. Ключи (владелец, на своём ПК, однократно)

```bash
age-keygen -o burmaldoza-backup.key     # печатает открытый ключ вида age1...
```

`burmaldoza-backup.key` — закрытый ключ: сохранить в менеджер паролей владельца и в офлайн-копию,
в репозиторий, чат и на сервер не класть. Открытый ключ `age1…` секретом не является.

### 7.2. Ночной дамп (сервер)

```bash
sudo install -d -m 700 -o deploy -g deploy /var/backups/burmaldoza /etc/burmaldoza
echo 'age1...открытый ключ владельца...' | sudo tee /etc/burmaldoza/backup-recipient.txt >/dev/null
sudo tee /usr/local/bin/burmaldoza-backup >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /srv/burmaldoza
out="/var/backups/burmaldoza/burmaldoza-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
docker compose -f docker-compose.prod.yml --env-file .env exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  | age -R /etc/burmaldoza/backup-recipient.txt > "$out.tmp"
test -s "$out.tmp"
mv "$out.tmp" "$out"
find /var/backups/burmaldoza -name '*.dump.age' -mtime +14 -delete
EOF
sudo chmod 755 /usr/local/bin/burmaldoza-backup
/usr/local/bin/burmaldoza-backup && ls -lh /var/backups/burmaldoza      # первый запуск вручную
( crontab -l 2>/dev/null; echo '30 3 * * * /usr/local/bin/burmaldoza-backup' ) | crontab -
```

Копии на сервере хранятся 14 дней.

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
# на сервере: пустая база для проверки
C="docker compose -f /srv/burmaldoza/docker-compose.prod.yml --env-file /srv/burmaldoza/.env"
$C exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" burmaldoza_restore_check'
```

```bash
# на ПК владельца, в Git Bash (Windows PowerShell 5 портит двоичный поток в конвейере):
# расшифровать свежую копию и восстановить в проверочную базу
age -d -i burmaldoza-backup.key burmaldoza-<дата>.dump.age | ssh deploy@<сервер> \
  "docker compose -f /srv/burmaldoza/docker-compose.prod.yml --env-file /srv/burmaldoza/.env exec -T postgres \
   sh -c 'pg_restore -U \"\$POSTGRES_USER\" -d burmaldoza_restore_check --no-owner --exit-on-error'"
```

```bash
# на сервере: сравнить с боевой базой и удалить проверочную
for db in burmaldoza burmaldoza_restore_check; do
  $C exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d $db -Atc \
    'select (select count(*) from users), (select count(*) from wallets), (select count(*) from ledger_entries)'"
done
$C exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" burmaldoza_restore_check'
```

Числа должны совпадать с боевой базой на момент копии (боевая могла вырасти с тех пор). Дату
успешной проверки записать в `dev/ProjectLog.md`.

## 9. Обновление и откат

Обновление — только на SHA из `main`, одобренный владельцем, после зелёного CI на этом SHA.

```bash
cd /srv/burmaldoza
C="docker compose -f docker-compose.prod.yml --env-file .env"
git rev-parse HEAD | tee -a ~/burmaldoza-deployed-shas.txt   # запомнить текущую версию
/usr/local/bin/burmaldoza-backup                             # свежая копия перед обновлением
git fetch origin && git checkout <новый SHA>
$C build --pull && $C up -d
```

Затем — проверки из раздела 6. Бот и API пересобираются вместе, так что `INTERNAL_API_TOKEN`
у них всегда один и тот же.

**Откат кода** (схема базы не менялась): вернуть прежний SHA из `~/burmaldoza-deployed-shas.txt`,
затем `git checkout <старый SHA> && $C build && $C up -d`.

**Откат, если новая версия применила миграцию.** API применяет `alembic upgrade head` при старте,
и старый код может не работать с новой схемой. `alembic downgrade` использовать, только если
downgrade этой миграции проверен в review. Иначе — восстановление из копии, сделанной перед
обновлением (простой сервиса, игровые действия после копии теряются):

```bash
$C stop api bot
$C exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
# на ПК владельца (Git Bash) — как в разделе 8, но в боевую базу:
#   age -d -i burmaldoza-backup.key <копия перед обновлением> | ssh deploy@<сервер> \
#     "... exec -T postgres sh -c 'pg_restore -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --no-owner --exit-on-error'"
git checkout <старый SHA> && $C build && $C up -d
```

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

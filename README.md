# Alpha — учёт восхождений альпинистского клуба

Прототип автоматизированной системы «Alpha» (см. ТЗ, ЛР № 1): серверная часть (REST API)
и клиентская часть — мобильное веб-приложение (PWA) для Android и iOS.

## Стек

| Часть | Технологии |
|---|---|
| Серверная часть | Python 3.12, Flask 3, SQLAlchemy 2, Gunicorn |
| Клиентская часть | HTML5, CSS3, JavaScript (PWA, mobile-first) |
| СУБД | SQLite (разработка) / PostgreSQL 16 (стенды) |
| ОС стендов | CentOS Stream 9 |

## Структура

```
server/            серверная часть (REST API)
  app/             пакет приложения: модели, API, начальные данные
  wsgi.py          точка входа WSGI
  requirements.txt зависимости Python
client/            клиентская часть (мобильное веб-приложение)
```

## Запуск прототипа без контейнеров

```bash
# серверная часть
cd server
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8000 --workers 2 --preload wsgi:app

# клиентская часть (в другом терминале)
cd client
python3 -m http.server 8080
```

Клиент: `http://<адрес стенда>:8080`, API: `http://<адрес стенда>:8000/api`.

## Запуск в Docker

Образ серверной части собирается из `Dockerfile` (база — `python:3.12-slim`):

```bash
docker build -t alpha-api:1.0 .
docker run -d --name alpha-api -p 8000:8000 alpha-api:1.0   # клиент и API на :8000, БД SQLite
```

Полный стенд (PostgreSQL + API + nginx) описан в `docker-compose.yaml`:

```bash
cp .env.example .env            # задать пароли
docker compose up -d --build    # сборка и запуск в фоне
docker compose logs -f          # вывод stdout/stderr сервисов
docker compose down             # остановка (данные остаются в ./volumes)
```

| Сервис | Образ | Назначение |
|---|---|---|
| `alpha-db` | `postgres:16-alpine` | СУБД, данные в `./volumes/postgres` |
| `alpha-api` | сборка из `Dockerfile` | REST API, логи в `./volumes/logs/api` |
| `alpha-web` | `nginx:1.27-alpine` | клиентская часть и прокси `/api`, логи в `./volumes/logs/nginx` |

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `DATABASE_URL` | строка подключения SQLAlchemy | `sqlite:///data/alpha.db` |
| `ALPHA_SECRET_KEY` | ключ подписи токенов | `dev-secret-change-me` |
| `ALPHA_LOG_DIR` | каталог логов | `./logs` |
| `ALPHA_SEED` | наполнить пустую БД демо-данными | `1` |

## API

| Метод | Путь | Доступ |
|---|---|---|
| GET | `/api/health`, `/api/stats` | все |
| POST | `/api/auth/register`, `/api/auth/login` | все |
| GET | `/api/auth/me` | авторизованные |
| GET | `/api/peaks`, `/api/groups`, `/api/climbers` | все |
| POST | `/api/peaks`, `/api/groups`, `/api/climbers` | руководитель, администратор |
| PUT | `/api/peaks/{id}` (если на вершину не было восхождений) | руководитель, администратор |
| POST | `/api/groups/{id}/members` | руководитель, администратор |
| GET, POST | `/api/admin/requests`, `/api/admin/requests/{id}/approve` | администратор |

## Демо-учётные записи

| Логин | Пароль | Роль |
|---|---|---|
| `anufriev` | `Anufriev2026!` | руководитель группы (Ануфриев Платон Дмитриевич) |
| `shemchuk` | `Shemchuk2026!` | администратор (Шемчук Мирон Денисович) |
| `smirnova` | `Climber2026!` | альпинист |

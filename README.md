# Supplier Mapping MVP

FastAPI + React (Vite) сервис для сопоставления поставщиков между прайсом продавца и каноническим справочником, с ролями Seller (по токену) и Admin (по логину/паролю).

## Структура репозитория
- `backend/app` — FastAPI + SQLModel, SQLite
- `frontend` — React + Vite + TypeScript UI
- `docker-compose.yml` — запуск двух сервисов
- `backend/app/seed.py` — демо-данные (справочник, прайс, токен)

## Быстрый старт (локально)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed            # создаст БД, демо-данные и выведет ссылку вида /s/<token>
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm install
npm run dev -- --host --port 5173
```

- Seller UI: `http://localhost:5173/s/<token>` (подставьте токен из seed-скрипта).
- Admin UI: `http://localhost:5173/` (логин/пароль из `.env`, по умолчанию admin/admin).

## Запуск через Docker Compose
```bash
cp .env.example .env   # при необходимости поменяйте ADMIN_USERNAME/ADMIN_PASSWORD
docker-compose up --build
```
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

## Основные модели (SQLite)
- `price_items` — строки нормализованного прайса.
- `price_supplier_groups` — агрегированные группы (ownerId + packetId + inn_norm + std_supplier_raw) с `items_count`.
- `suppliers` — справочник канонических поставщиков.
- `supplier_mappings` — заявки/связки со статусами `PENDING | APPROVED | REJECTED`.
- `seller_issues` — сообщения “не нашёл поставщика”.
- `seller_tokens` — одноразовые токены входа продавца (ownerId + packetId + expires_at).

## Ключевые эндпоинты
- `POST /api/import/price_items` — загрузка нормализованных строк прайса, агрегация групп.
- `GET /api/seller/groups?token=...` — группы поставщиков для продавца, статусы UNMAPPED/PENDING/APPROVED/REJECTED.
- `POST /api/seller/mappings` — заявка на сопоставление `{token, group_id, canonical_supplier_id}`.
- `POST /api/seller/issues` — “не нашёл поставщика”.
- `GET /api/seller/suppliers?q=` — поиск по справочнику для выбора каноники.
- `POST /api/admin/login` — логин (cookie-сессия), логин/пароль из env.
- `GET/POST/PUT/DELETE /api/admin/suppliers` — CRUD справочника.
- `GET /api/admin/mappings/pending` — очередь модерации.
- `POST /api/admin/mappings/{id}/approve|reject` — действия модератора.
- `GET /api/admin/moderation/history?limit=&offset=&q=` — история решений (append-only).
- `GET /api/admin/issues` — список Issues.
- `GET /api/analytics/mappings?from=&to=` — только APPROVED связи для аналитики.
- `GET /api/analytics/mappings/by_packet?packetId=...&ownerId=...` — approved связи по конкретному прайсу.

## Примеры cURL
Импорт прайса:
```bash
curl -X POST http://localhost:8000/api/import/price_items \
  -H "Content-Type: application/json" \
  -d '[{"ownerId":"o1","packetId":"p1","inn":"7701234567","std_supplier":"Росско","itemId":"i1"}]'
```

Аналитика (approved связи):
```bash
curl "http://localhost:8000/api/analytics/mappings?from=2023-01-01&to=2023-12-31"
curl "http://localhost:8000/api/analytics/mappings/by_packet?packetId=demo-packet&ownerId=demo-owner"
```

Логин в админку (cookie сохранится в файл):
```bash
curl -i -c cookies.txt -X POST http://localhost:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

## Сид-данные (демо)
`python -m app.seed` создаёт:
- 2 канонических поставщика (Росско, Берг)
- 150 строк прайса для одного `ownerId`/`packetId` (2 группы: 100 и 50 товаров)
- seller token на 7 дней и печатает ссылку `/s/<token>`

## Примечания по безопасности
- Seller видит только свои данные по токену (ownerId + packetId в токене).
- Админка доступна только после логина, с cookie-сессией (`SESSION_SECRET` в `.env`).
- CORS настроен на `localhost:5173`.

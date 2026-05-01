# Yozuvchim — AI Academic Writing Bot + Web App

Hybrid monorepo for the academic writing assistant.

## Stack

| Component | Tech |
|-----------|------|
| **Backend API** | NestJS 11 + TypeScript + Prisma + PostgreSQL + Redis + JWT |
| **Frontend** | React 19 + Vite + TypeScript + Tailwind + Radix UI + Zustand |
| **Bot Worker** | Python 3.12 + aiogram + SQLAlchemy + python-docx + python-pptx |
| **Infra** | Docker Compose, nginx |

## Repo Structure

```
yozuvchim/
├── backend/              NestJS API (auth, users, orders, payments, admin)
├── frontend/             React + Vite SPA
├── bot/                  Python bot worker (Telegram + AI + DOCX/PPTX export)
├── nginx/                nginx config + Dockerfile that builds the SPA
├── docker-compose.yml    All services
└── .env.example          Copy to .env and fill in
```

## Local Development (Docker)

```bash
cp .env.example .env
# Fill in BOT_TOKEN, BOT_USERNAME, DEEPSEEK_API_KEY, etc.

docker compose up -d --build
```

Open <http://localhost:8080>.

## Production Deploy

Same as local, but with `.env` containing production values and `WEB_APP_URL` pointing to your domain.

```bash
git pull
docker compose up -d --build
```

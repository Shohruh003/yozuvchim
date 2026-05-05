# Production Deployment Guide

This walks through deploying yozuvchim to a Linux VPS (Ubuntu 22.04+) with
HTTPS, automated backups, and proper migrations.

> Estimated time: **20–30 minutes** for a fresh server.

---

## 1. Prerequisites

On your **server**:
- Ubuntu 22.04+ (or any Docker-friendly Linux)
- Public IP and a domain (e.g. `yozuvchim.uz`) with `A` record pointing at the IP
- Ports **80** and **443** open in the firewall
- `git`, `curl`, `openssl`

Install Docker if not already installed:
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
# log out + back in so the group takes effect
```

In **@BotFather** (Telegram):
- Create a *production* bot (separate from your dev bot) and copy its `BOT_TOKEN`
- Run `/setdomain` and set it to your public domain (e.g. `yozuvchim.uz`)
- Run `/setmenubutton` and point it to `https://yozuvchim.uz/`

---

## 2. Clone and configure

```bash
sudo mkdir -p /opt/yozuvchim
sudo chown "$USER" /opt/yozuvchim
cd /opt
git clone https://github.com/Shohruh003/yozuvchim.git
cd yozuvchim
```

Create a fresh `.env` from the production template:
```bash
cp .env.production.example .env
```

Generate strong secrets:
```bash
chmod +x scripts/*.sh
./scripts/generate-secrets.sh
```
Paste the output into `.env`, replacing the empty `JWT_SECRET`,
`JWT_REFRESH_SECRET`, `POSTGRES_PASSWORD`, and `ADMIN_LOGIN_PASSWORD` lines.

Then edit `.env` and fill in the rest:
- `PUBLIC_DOMAIN` — your domain
- `ACME_EMAIL` — for Let's Encrypt notifications
- `BOT_TOKEN`, `BOT_USERNAME` — production bot
- `DEEPSEEK_API_KEY` — your AI provider key
- `SUPERADMIN_IDS` — your Telegram numeric ID (comma-separated for multiple)
- `ADMIN_LOGIN_USERNAME` — pick a username (e.g. `admin`)

Lock the file down:
```bash
chmod 600 .env
```

---

## 3. First boot

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Watch logs until everything is healthy:
```bash
docker compose logs -f --tail=50
# Ctrl+C to stop tailing
```

Caddy will obtain a Let's Encrypt cert automatically the first time someone
hits the domain (~10 seconds after a request to `https://your-domain`).

Visit `https://your-domain/admin/login` and sign in with the
`ADMIN_LOGIN_USERNAME` / `ADMIN_LOGIN_PASSWORD` you set.

---

## 4. Lock down credentials

After your first successful login:

1. Open `/admin/settings` → change the username AND password to fresh values.
2. SSH back to the server and **remove** the bootstrap lines from `.env`:
   ```diff
   - ADMIN_LOGIN_USERNAME=admin
   - ADMIN_LOGIN_PASSWORD=...
   ```
   The credentials now live in the DB only (bcrypt-hashed).
3. Restart backend so it picks up the trimmed env:
   ```bash
   docker compose restart backend
   ```

---

## 5. Add a payment card

Open `/admin/cards` → "Yangi karta" → enter your real card number, holder
name, bank. Toggle it active. The bot and the user-facing top-up page will
start showing it immediately.

---

## 6. Automated backups

Add the daily backup to root's crontab:
```bash
sudo crontab -e
```
Append:
```
0 3 * * * cd /opt/yozuvchim && ./scripts/backup-db.sh >> /var/log/yozuvchim-backup.log 2>&1
30 3 * * * cd /opt/yozuvchim && ./scripts/cleanup-old-files.sh >> /var/log/yozuvchim-cleanup.log 2>&1
```

Default retention:
- DB backups: 14 days (override with `BACKUP_RETAIN_DAYS=N` in `.env`)
- Generated DOCX/PPTX: 30 days (override with `FILES_RETAIN_DAYS=N` in `.env`)

Backups land in `/opt/yozuvchim/backups/`. Consider syncing them off-box:
```
rclone sync /opt/yozuvchim/backups remote:yozuvchim-backups
```

---

## 7. Updating

```bash
cd /opt/yozuvchim
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The backend container automatically applies any new Prisma migrations on
boot via `prisma migrate deploy`.

---

## 8. Common operations

**Tail logs**
```bash
docker compose logs -f backend
docker compose logs -f bot
docker compose logs -f caddy
```

**Restart a single service**
```bash
docker compose restart backend
```

**Manual backup**
```bash
./scripts/backup-db.sh
```

**Restore a backup**
```bash
gunzip < backups/yozuvchim-20260101-0300.sql.gz | \
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

**Promote a Telegram user to superadmin** (no shell needed — do it from the panel)
- Open `/admin/users`, click the user, then "Superadmin qilib tayinlash".

---

## 9. Troubleshooting

**HTTPS cert not issued**
- Make sure ports 80 and 443 are open in your firewall and not already used.
- Check Caddy logs: `docker compose logs caddy`.
- DNS must already resolve to the server when Caddy first starts.

**Backend keeps restarting**
- `docker compose logs backend` — look for missing env vars or DB connection errors.
- Verify `JWT_SECRET` is non-empty (entrypoint won't crash but JWTs won't verify).

**Migrations fail with `P3005`**
- Means the DB has tables but no `_prisma_migrations` record. The entrypoint
  handles this automatically on first boot. If you imported a backup from
  another deployment, run inside the container:
  ```bash
  docker compose exec backend npx prisma migrate resolve --applied 20260101000000_init
  docker compose restart backend
  ```

**Bot polling errors after deploy**
- Make sure only one bot instance is running. If you still have a dev bot
  polling with the same token, stop it.

---

## 10. Hardening checklist (after launch)

- [ ] `chmod 600 .env` on the server
- [ ] Removed `ADMIN_LOGIN_*` from `.env` after changing via panel
- [ ] Strong `POSTGRES_PASSWORD` (≥ 24 chars, generated)
- [ ] Strong `JWT_SECRET` and `JWT_REFRESH_SECRET` (≥ 64 chars each)
- [ ] Cron entries for `backup-db.sh` and `cleanup-old-files.sh`
- [ ] Backups synced off-server (rclone / S3 / etc.)
- [ ] `ufw` enabled, only 22/80/443 open
- [ ] SSH key-only auth, no root password login
- [ ] Caddy `acme_ca` line is **not** the staging URL (in `caddy/Caddyfile`)

# Deploying Orodruin (production)

Target: an Ubuntu server (e.g. OVH VPS) serving `orodruin.dev` over HTTPS. Layout
assumes the repo lives at `/opt/orodruin` and runs under a dedicated `orodruin` user.

## 0. Prerequisites

- Ubuntu 22.04+ with `nginx`, `docker` + `docker compose`, `python3.11+`, `nodejs 20+`.
- A DNS A record for `orodruin.dev` (and `www`) pointing at the server.
- **At least 2 GB RAM.** Add swap if the box is small:
  ```bash
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```

## 1. Get the code

```bash
sudo useradd -m -s /bin/bash orodruin
sudo git clone https://github.com/Dev-next-gen/orodruin.git /opt/orodruin
sudo chown -R orodruin:orodruin /opt/orodruin
```

## 2. Database

```bash
cd /opt/orodruin
docker compose up -d db          # PostgreSQL 16 on :5544
```

## 3. Backend

```bash
sudo -u orodruin bash
cd /opt/orodruin/backend
cp .env.example .env
#  -> edit .env: fill your keys, and set PUBLIC_MODE=true  (important, see below)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m app.ingest.run --once  # initial load
exit
```

**Set `PUBLIC_MODE=true` in `.env`.** In public mode Orodruin hides the Settings panel,
refuses key/LLM changes over HTTP, and rate-limits the AI analyst (`CHAT_RATE_PER_MIN`)
so visitors cannot burn your LLM credit.

## 4. Frontend build

```bash
cd /opt/orodruin/frontend
npm ci
npm run build                    # outputs frontend/dist (served by nginx)
```

## 5. systemd services

```bash
sudo cp /opt/orodruin/deploy/orodruin-api.service /etc/systemd/system/
sudo cp /opt/orodruin/deploy/orodruin-ingest.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orodruin-api orodruin-ingest
```

## 6. nginx + TLS

```bash
sudo cp /opt/orodruin/deploy/nginx-orodruin.conf /etc/nginx/sites-available/orodruin
sudo ln -s /etc/nginx/sites-available/orodruin /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d orodruin.dev -d www.orodruin.dev
```

Orodruin is now live at **https://orodruin.dev**.

## Updating

```bash
cd /opt/orodruin && sudo -u orodruin git pull
cd frontend && sudo -u orodruin npm ci && sudo -u orodruin npm run build
sudo systemctl restart orodruin-api orodruin-ingest
```

## Notes

- The `GOOGLE_MAPS_KEY` is the only key sent to the browser — restrict it by HTTP
  referrer (`orodruin.dev/*`) in the Google Cloud Console.
- Watch `journalctl -u orodruin-api -f` and `-u orodruin-ingest -f` for logs.
- If a layer is empty, the upstream source is usually rate-limiting — it recovers.

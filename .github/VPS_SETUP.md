# VPS Setup Guide (Hostinger)

One-time setup on the VPS before GitHub Actions deployments will work.

---

## 1. GitHub Secrets to Configure

Go to GitHub → your repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `VPS_HOST` | Your Hostinger VPS IP or hostname |
| `VPS_USER` | SSH username (e.g. `root`) |
| `VPS_SSH_KEY` | Contents of your **private** SSH key (e.g. `~/.ssh/id_ed25519`) |
| `VPS_PORT` | SSH port, usually `22` |
| `NEXT_PUBLIC_API_URL` | e.g. `https://yourdomain.com/uwapi` |

To generate a dedicated deploy key:
```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy
# Add public key to VPS authorized_keys:
# cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
# Add private key file contents as VPS_SSH_KEY secret
```

---

## 2. VPS: Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # if not running as root
```

---

## 3. VPS: Create the `.env` files

**Root `.env`** — only the image prefix for docker-compose:
```bash
cd /opt/deployment/code-base/AI_Collections
cp .env.example .env
nano .env   # set GHCR_IMAGE_PREFIX=ghcr.io/yutrix-labs/ai-collections
```

**Listening agent `.env`** — LiveKit credentials:
```bash
cd backend/listening-agent
cp .env.example .env
nano .env   # fill in LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
```

The frontend has `NEXT_PUBLIC_API_URL` baked in at image build time via the `NEXT_PUBLIC_API_URL` GitHub secret — no runtime env needed.
The backend reads all config from its bundled `application.yml`.

---

## 4. VPS: Authenticate Docker with GitHub Container Registry

GitHub Actions pushes images to ghcr.io. The VPS needs to pull them.

Create a GitHub Personal Access Token (PAT) with `read:packages` scope, then:
```bash
echo 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 | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

---

## 5. VPS: First-time startup

```bash
cd /opt/deployment/code-base/AI_Collections
docker compose pull
docker compose up -d
docker compose ps   # verify all three are running
```

After this, GitHub Actions handles all subsequent deploys automatically on push to `main`.

---

## 6. Nginx Reverse Proxy (recommended)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

```nginx
# /etc/nginx/sites-available/aiassistant.yutrix.io
server {
    listen 80;
    server_name aiassistant.yutrix.io;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }

    # Backend API + WebSocket (STOMP)
    location /uwapi/ {
        proxy_pass http://localhost:8080/uwapi/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/aiassistant.yutrix.io /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d aiassistant.yutrix.io
```

---

## Useful Docker commands

```bash
# View logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f listening-agent

# Restart a service
docker compose restart backend

# Pull latest and redeploy manually
docker compose pull && docker compose up -d
```

# Accento production deployment

This guide deploys Accento without exposing its API, Redis, or MongoDB directly.
The only Accento port published on the VPS is `127.0.0.1:8010`, which the
existing host reverse proxy uses. Replace `YOUR_VPS_IP`, `YOUR_DEPLOY_USER`,
and `YOUR_DOMAIN` locally; never commit their real values.

## 1. Check the VPS before changing it

SSH to the server and identify the existing reverse proxy. Do not install a
second proxy on ports 80 and 443.

```bash
ssh root@YOUR_VPS_IP
ss -ltnp | grep -E ':(80|443)\s'
nginx -v
caddy version
docker --version
docker compose version
free -h
df -h
```

The supplied host configuration is for Nginx. If Caddy or Traefik owns ports
80/443, translate only the hostname route; do not replace the existing proxy.
An 8 GB VPS and at least 25 GB of free disk are recommended for the ML worker
and its container images.

## 2. Create the DNS record

In your DNS provider, open the DNS records for `YOUR_DOMAIN` and add:

- Type: `A`
- Name: `accento`
- Points to: your VPS public IP address
- TTL: default (typically `14400`)

Remove only conflicting records for the new hostname. Leave the records for
the root domain and every other subdomain unchanged. Verify propagation:

```bash
dig +short YOUR_SUBDOMAIN.YOUR_DOMAIN A
```

## 3. Prepare the deployment account and directory

Use a dedicated non-root account for deployment. Docker group
membership is powerful, so never use this SSH key for unrelated automation.

```bash
ssh root@YOUR_VPS_IP
install -d -o YOUR_DEPLOY_USER -g YOUR_DEPLOY_USER -m 750 /opt/accento
usermod -aG docker YOUR_DEPLOY_USER
```

Log out and back in as the deployment user, then confirm Docker works without
`sudo`:

```bash
ssh YOUR_DEPLOY_USER@YOUR_VPS_IP
docker info
```

If Docker is not already installed, install Docker Engine and the Compose
plugin from Docker's official Ubuntu repository before continuing.

## 4. Create the production environment file

Generate URL-safe database passwords:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Create `/opt/accento/.env` as the deployment user with mode `600`:

```bash
cd /opt/accento
umask 077
touch .env
chmod 600 .env
nano .env
```

Use this template and substitute the generated passwords:

```dotenv
APP_NAME=accento
ENV=production
DEBUG=False

MONGO_USER=accento_admin
MONGO_PASSWORD=FIRST_GENERATED_HEX_VALUE
MONGO_DB=accento
REDIS_PASSWORD=SECOND_GENERATED_HEX_VALUE

ALLOWED_HOSTS=YOUR_SUBDOMAIN.YOUR_DOMAIN,api
DAILY_ANALYSIS_LIMIT=4
RESULT_CACHE_SECONDS=86400
ERROR_CACHE_SECONDS=300
RESULT_RETENTION_DAYS=30
ACCENT_THRESHOLD=0.6
MAX_UPLOAD_BYTES=26214400
UPLOAD_RETENTION_SECONDS=1800
```

## 5. Create the GitHub Actions deployment key

On a trusted local computer, create a dedicated key without overwriting an
existing key:

```bash
ssh-keygen -t ed25519 -f ./accento_github_deploy -C accento-github-actions
ssh-copy-id -i ./accento_github_deploy.pub YOUR_DEPLOY_USER@YOUR_VPS_IP
```

Add these GitHub repository secrets under **Settings → Secrets and variables →
Actions**:

- `VPS_HOST`: your VPS address
- `VPS_USER`: your dedicated deployment username
- `VPS_SSH_PRIVATE_KEY`: the complete contents of `accento_github_deploy`
- `VPS_KNOWN_HOSTS`: a verified SSH host-key line for this server

Obtain the host key from the server console/root session so it is not accepted
blindly over the network:

```bash
awk -v host="YOUR_VPS_IP" '{print host " " $1 " " $2}' /etc/ssh/ssh_host_ed25519_key.pub
```

The workflow publishes three images to GitHub Container Registry. If the GHCR
packages remain private, log the deployment user into GHCR once with a GitHub
token that has only `read:packages`. Otherwise, mark the three packages public;
the images contain no application secrets.

## 6. Push the project to GitHub

Review the changes, commit them, and push `main`:

```bash
git add .
git commit -m "Deploy Accento web application"
git push origin main
```

The `Build and deploy` workflow will:

1. Test the Python upload security rules and build the React app.
2. Build versioned API, worker, and web images.
3. Publish the images to GHCR.
4. Copy the production Compose definition to `/opt/accento`.
5. Pull and start only the `accento` Compose project.
6. Verify `http://127.0.0.1:8010/healthz`.

The first worker build is large because it embeds the speech models. Later
builds use GitHub's build cache.

## 7. Add the Nginx hostname without affecting other services

For an existing Nginx proxy, copy `deploy/nginx-host.conf` to its own site file:

```bash
scp deploy/nginx-host.conf root@YOUR_VPS_IP:/etc/nginx/sites-available/YOUR_SUBDOMAIN.YOUR_DOMAIN
ssh root@YOUR_VPS_IP
ln -s /etc/nginx/sites-available/YOUR_SUBDOMAIN.YOUR_DOMAIN /etc/nginx/sites-enabled/YOUR_SUBDOMAIN.YOUR_DOMAIN
nginx -t
systemctl reload nginx
```

Do not reload Nginx unless `nginx -t` succeeds. This adds one hostname and does
not change any existing server block.

Once DNS resolves and the workflow reports a healthy deployment, issue the TLS
certificate:

```bash
certbot --nginx -d YOUR_SUBDOMAIN.YOUR_DOMAIN --redirect
nginx -t
systemctl reload nginx
```

## 8. Verify security and operation

```bash
curl -I https://YOUR_SUBDOMAIN.YOUR_DOMAIN
curl https://YOUR_SUBDOMAIN.YOUR_DOMAIN/api/health/ready
ss -ltnp | grep -E ':(8010|6379|27017)\s'
docker compose --env-file /opt/accento/.env --env-file /opt/accento/deploy.env -f /opt/accento/docker-compose.yml ps
```

Expected exposure:

- Nginx: public ports 80/443.
- Accento web: loopback-only port 8010.
- Redis and MongoDB: no host ports.

Upload one supported video in the browser and follow worker logs if needed:

```bash
cd /opt/accento
docker compose --env-file .env --env-file deploy.env logs --tail=100 api worker web
```

## Rollback

Every deployment uses the Git commit SHA as its image tag. To roll back, put a
previous successful SHA in `/opt/accento/deploy.env`, then run:

```bash
cd /opt/accento
docker compose --env-file .env --env-file deploy.env pull
docker compose --env-file .env --env-file deploy.env up -d --wait
```

Never delete the `mongo_data` volume during a rollback.

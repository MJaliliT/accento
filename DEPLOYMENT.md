# Accento production deployment

This guide deploys Accento at `https://accento.mjalili.com` without exposing
its API, Redis, or MongoDB directly. The only Accento port published on the VPS
is `127.0.0.1:8010`, which the existing host reverse proxy uses.

## 1. Check the VPS before changing it

SSH to the server and identify the existing reverse proxy. Do not install a
second proxy on ports 80 and 443.

```bash
ssh root@72.60.165.248
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

## 2. Create the DNS record in Hostinger

In hPanel, open **Domains → mjalili.com → DNS / Nameservers → DNS records** and
add:

- Type: `A`
- Name: `accento`
- Points to: `72.60.165.248`
- TTL: default (typically `14400`)

Remove only conflicting `accento` A/AAAA/CNAME records. Leave the records for
the root domain and every other subdomain unchanged. Verify propagation:

```bash
dig +short accento.mjalili.com A
```

## 3. Prepare the deployment account and directory

Use the existing non-root `mohammad` account for deployment. Docker group
membership is powerful, so never use this SSH key for unrelated automation.

```bash
ssh root@72.60.165.248
install -d -o mohammad -g mohammad -m 750 /opt/accento
usermod -aG docker mohammad
```

Log out and back in as `mohammad`, then confirm Docker works without `sudo`:

```bash
ssh mohammad@72.60.165.248
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

Create `/opt/accento/.env` as `mohammad` with mode `600`:

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

ALLOWED_HOSTS=accento.mjalili.com,api
DAILY_ANALYSIS_LIMIT=4
RESULT_CACHE_SECONDS=86400
ERROR_CACHE_SECONDS=300
RESULT_RETENTION_DAYS=30
ACCENT_THRESHOLD=0.6
```

## 5. Create the GitHub Actions deployment key

On a trusted local computer, create a dedicated key without overwriting an
existing key:

```bash
ssh-keygen -t ed25519 -f ./accento_github_deploy -C accento-github-actions
ssh-copy-id -i ./accento_github_deploy.pub mohammad@72.60.165.248
```

Add these GitHub repository secrets under **Settings → Secrets and variables →
Actions**:

- `VPS_HOST`: `72.60.165.248`
- `VPS_USER`: `mohammad`
- `VPS_SSH_PRIVATE_KEY`: the complete contents of `accento_github_deploy`
- `VPS_KNOWN_HOSTS`: a verified SSH host-key line for this server

Obtain the host key from the server console/root session so it is not accepted
blindly over the network:

```bash
awk '{print "72.60.165.248 " $1 " " $2}' /etc/ssh/ssh_host_ed25519_key.pub
```

The workflow publishes three images to GitHub Container Registry. If the GHCR
packages remain private, log the `mohammad` user into GHCR once with a GitHub
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

1. Test the Python URL security rules and build the React app.
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
scp deploy/nginx-host.conf root@72.60.165.248:/etc/nginx/sites-available/accento.mjalili.com
ssh root@72.60.165.248
ln -s /etc/nginx/sites-available/accento.mjalili.com /etc/nginx/sites-enabled/accento.mjalili.com
nginx -t
systemctl reload nginx
```

Do not reload Nginx unless `nginx -t` succeeds. This adds one hostname and does
not change any existing server block.

Once DNS resolves and the workflow reports a healthy deployment, issue the TLS
certificate:

```bash
certbot --nginx -d accento.mjalili.com --redirect
nginx -t
systemctl reload nginx
```

## 8. Verify security and operation

```bash
curl -I https://accento.mjalili.com
curl https://accento.mjalili.com/api/health/ready
ss -ltnp | grep -E ':(8010|6379|27017)\s'
docker compose --env-file /opt/accento/.env --env-file /opt/accento/deploy.env -f /opt/accento/docker-compose.yml ps
```

Expected exposure:

- Nginx: public ports 80/443.
- Accento web: loopback-only port 8010.
- Redis and MongoDB: no host ports.

Submit one public YouTube URL in the browser and follow worker logs if needed:

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

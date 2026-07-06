# AWS Remote Server Installation Guide

This guide installs the Xtract.io for Chubb Arabia underwriting workbench on a single AWS EC2 server. It uses:

- FastAPI backend running on `127.0.0.1:8000` under `systemd`
- React frontend built with Vite and served by Nginx
- Nginx reverse proxy for `/api/*` and `/health`
- Local SQLite/artifact storage under `artifacts/`

The setup is suitable for demos, internal prototypes, and controlled pilots. Before production use, add enterprise authentication, TLS certificate automation, backups, monitoring, audit retention, and formal secrets management.

## 1. AWS Server Prerequisites

Recommended baseline:

- EC2 instance: Ubuntu 22.04 LTS or 24.04 LTS
- Architecture: x86_64
- Size: at least `t3.large` for smoother model/SHAP workloads; `t3.medium` can work for lighter demos
- Disk: at least 40 GB gp3 EBS
- Security group inbound rules:
  - TCP `22` from your office/VPN IP only
  - TCP `80` from allowed users or `0.0.0.0/0` for public demo access
  - TCP `443` once TLS is configured
- Do not expose backend port `8000` or Vite port `5173` publicly in production mode.

Optional but recommended:

- Elastic IP attached to the instance
- DNS record such as `xtract-demo.example.com`
- AWS Systems Manager Session Manager for SSH-less access
- EBS snapshot policy for backups

## 2. Connect To The Server

From your machine:

```bash
ssh -i /path/to/key.pem ubuntu@<EC2_PUBLIC_IP>
```

Update the OS:

```bash
sudo apt update
sudo apt -y upgrade
sudo reboot
```

Reconnect after reboot.

## 3. Install System Packages

```bash
sudo apt update
sudo apt install -y \
  git \
  curl \
  build-essential \
  python3 \
  python3-venv \
  python3-pip \
  nginx
```

Install Node.js 20 LTS from NodeSource:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version
npm --version
```

## 4. Create Application User And Directory

```bash
sudo useradd --system --create-home --shell /bin/bash xtract
sudo mkdir -p /opt/xtract-io-chubb
sudo chown xtract:xtract /opt/xtract-io-chubb
```

Clone or copy the repo into `/opt/xtract-io-chubb`.

Using Git:

```bash
sudo -iu xtract
cd /opt/xtract-io-chubb
git clone <YOUR_REPO_URL> .
exit
```

If the repo is already copied by another deployment mechanism, ensure ownership is correct:

```bash
sudo chown -R xtract:xtract /opt/xtract-io-chubb
```

## 5. Install Python Dependencies

```bash
sudo -iu xtract
cd /opt/xtract-io-chubb
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
exit
```

## 6. Install And Build The Frontend

For the Nginx same-origin deployment, leave `VITE_API_BASE_URL` empty at build time. The browser will call `/api/...`, and Nginx will proxy those calls to FastAPI.

```bash
sudo -iu xtract
cd /opt/xtract-io-chubb/frontend
npm ci
VITE_API_BASE_URL="" npm run build
exit
```

The built frontend will be in:

```text
/opt/xtract-io-chubb/frontend/dist
```

## 7. Configure Environment Variables

Create a server-side environment file:

```bash
sudo tee /etc/xtract-io-chubb.env >/dev/null <<'EOF'
UNDERWRITING_MODEL_ROWS=2500
UNDERWRITING_DB_PATH=/opt/xtract-io-chubb/artifacts/underwriting.db
UNSTRUCTURED_UPLOAD_DIR=/opt/xtract-io-chubb/artifacts/uploads
UNSTRUCTURED_MAX_UPLOAD_MB=25
GEMINI_EXTRACTION_MODEL=gemini-3.5-flash
GEMINI_API_KEY=replace_with_real_key_when_needed
EOF
```

Protect it:

```bash
sudo chown root:xtract /etc/xtract-io-chubb.env
sudo chmod 640 /etc/xtract-io-chubb.env
```

Create writable artifact directories:

```bash
sudo -iu xtract
mkdir -p /opt/xtract-io-chubb/artifacts/uploads
mkdir -p /opt/xtract-io-chubb/artifacts/quotes
exit
```

Notes:

- `GEMINI_API_KEY` is required only for real unstructured extraction.
- Without a valid Gemini key, the rest of the workbench still runs, but extraction calls will fail.
- Keep `.env` and `/etc/xtract-io-chubb.env` out of Git.

## 8. Create The FastAPI Systemd Service

```bash
sudo tee /etc/systemd/system/xtract-api.service >/dev/null <<'EOF'
[Unit]
Description=Xtract.io for Chubb Arabia FastAPI backend
After=network.target

[Service]
Type=simple
User=xtract
Group=xtract
WorkingDirectory=/opt/xtract-io-chubb
EnvironmentFile=/etc/xtract-io-chubb.env
ExecStart=/opt/xtract-io-chubb/.venv/bin/uvicorn underwriting_system.api:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

Start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable xtract-api
sudo systemctl start xtract-api
sudo systemctl status xtract-api --no-pager
```

Check the backend locally on the server:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 9. Configure Nginx

Create an Nginx site:

```bash
sudo tee /etc/nginx/sites-available/xtract-io-chubb >/dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    root /opt/xtract-io-chubb/frontend/dist;
    index index.html;

    client_max_body_size 30M;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF
```

Enable it:

```bash
sudo ln -sf /etc/nginx/sites-available/xtract-io-chubb /etc/nginx/sites-enabled/xtract-io-chubb
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Open the app:

```text
http://<EC2_PUBLIC_IP>/
```

Or, if DNS is configured:

```text
http://xtract-demo.example.com/
```

## 10. Optional TLS With Certbot

After DNS points to the server, install Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Issue and install a certificate:

```bash
sudo certbot --nginx -d xtract-demo.example.com
```

Test renewal:

```bash
sudo certbot renew --dry-run
```

After TLS is enabled, use:

```text
https://xtract-demo.example.com/
```

## 11. Optional Streamlit Analytics App

The React workbench already includes the model section, so Streamlit is optional. If you still want to expose the older analytics app, run it behind Nginx on localhost only.

Create a service:

```bash
sudo tee /etc/systemd/system/xtract-streamlit.service >/dev/null <<'EOF'
[Unit]
Description=Xtract.io Streamlit analytics app
After=network.target

[Service]
Type=simple
User=xtract
Group=xtract
WorkingDirectory=/opt/xtract-io-chubb
EnvironmentFile=/etc/xtract-io-chubb.env
ExecStart=/opt/xtract-io-chubb/.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

Start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable xtract-streamlit
sudo systemctl start xtract-streamlit
```

Then add an Nginx location if you need browser access. Streamlit under a subpath can require extra configuration; for demos, a separate subdomain is simpler.

## 12. Smoke Test

From your laptop:

```bash
curl -fsS http://<EC2_PUBLIC_IP>/health
```

In the browser:

1. Open `http://<EC2_PUBLIC_IP>/`.
2. Confirm the Process Flow screen loads.
3. Open **Unstructured Intake**.
4. Upload a `.pdf`, `.eml`, `.csv`, `.xlsx`, or `.xls` file.
5. Run **Extract** only after `GEMINI_API_KEY` is configured.
6. Approve the extracted values into Triage.
7. Run enrichment, underwriting, quote generation, and bind.

On the server, check logs:

```bash
sudo journalctl -u xtract-api -f
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 13. Updating The Application

```bash
sudo -iu xtract
cd /opt/xtract-io-chubb
git pull
.venv/bin/pip install -r requirements.txt
cd frontend
npm ci
VITE_API_BASE_URL="" npm run build
exit

sudo systemctl restart xtract-api
sudo systemctl reload nginx
```

If dependencies or Python version changed materially, rebuild the virtual environment instead of reusing it.

## 14. Backup And Persistence

The current prototype stores state and generated files locally:

```text
/opt/xtract-io-chubb/artifacts/underwriting.db
/opt/xtract-io-chubb/artifacts/uploads/
/opt/xtract-io-chubb/artifacts/quotes/
```

Recommended backup options:

- EBS snapshots for the instance volume
- Scheduled copy of `artifacts/` to S3
- For multi-user production, replace local SQLite with a managed database such as RDS PostgreSQL and move uploaded documents/PDFs to S3

Minimum manual backup:

```bash
sudo tar -czf /tmp/xtract-artifacts-$(date +%Y%m%d-%H%M%S).tgz -C /opt/xtract-io-chubb artifacts
```

## 15. Security Hardening Checklist

Before any external or production-facing use:

- Enable HTTPS with a valid certificate.
- Restrict SSH to a VPN, bastion, or AWS Systems Manager.
- Add authentication and role-based authorization to the app.
- Remove public access to ports other than `80` and `443`.
- Store `GEMINI_API_KEY` in AWS Secrets Manager or SSM Parameter Store instead of a flat file.
- Add CloudWatch logs and alarms for service health and disk usage.
- Add regular backups for `artifacts/`.
- Review CORS configuration. The backend currently allows all origins for prototype convenience.
- Add malware scanning and content validation for uploaded files if used outside a controlled demo.
- Replace generated/simulated assumptions with governed production data sources before operational pricing decisions.

## 16. Troubleshooting

Backend fails to start:

```bash
sudo systemctl status xtract-api --no-pager
sudo journalctl -u xtract-api -n 200 --no-pager
```

Frontend loads but API calls fail:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://localhost/health
sudo nginx -t
```

Upload fails with a large file:

- Increase `UNSTRUCTURED_MAX_UPLOAD_MB` in `/etc/xtract-io-chubb.env`.
- Increase `client_max_body_size` in Nginx.
- Restart backend and reload Nginx.

Extraction fails:

- Confirm `GEMINI_API_KEY` is set in `/etc/xtract-io-chubb.env`.
- Restart `xtract-api` after changing the key.
- Check `sudo journalctl -u xtract-api -n 100 --no-pager`.

Static assets appear stale after update:

```bash
cd /opt/xtract-io-chubb/frontend
sudo -u xtract VITE_API_BASE_URL="" npm run build
sudo systemctl reload nginx
```

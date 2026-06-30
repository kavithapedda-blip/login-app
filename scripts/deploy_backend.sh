#!/usr/bin/env bash
#
# Deploy the FastAPI backend on the EC2 host.
#
# Invoked by .github/workflows/deploy.yml (deploy-backend job) over SSH AFTER
# the code has been scp'd to /home/ubuntu/app, i.e. the layout on the host is:
#   /home/ubuntu/app/backend/   (main.py, requirements.txt, ...)
#   /home/ubuntu/app/scripts/   (this script)
#
# The workflow exports JWT_SECRET and ALLOWED_ORIGINS into the environment
# before running this script; they are baked into the systemd unit below.
set -euo pipefail

APP_DIR="/home/ubuntu/app"
BACKEND_DIR="${APP_DIR}/backend"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_NAME="login-app"
RUN_USER="ubuntu"

echo ">> Deploying backend from ${BACKEND_DIR}"

# --- Python virtualenv + dependencies -------------------------------------
if [ ! -d "${VENV_DIR}" ]; then
  echo ">> Creating virtualenv at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"

# --- systemd unit (authoritative; generated with the live secrets) --------
# Values are written via the environment passed in by the workflow.
echo ">> Writing systemd unit /etc/systemd/system/${SERVICE_NAME}.service"
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<UNIT
[Unit]
Description=Practice FastAPI Login App
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${BACKEND_DIR}
Environment="JWT_SECRET=${JWT_SECRET:-}"
Environment="ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-*}"
ExecStart=${VENV_DIR}/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

# --- (re)start the service -------------------------------------------------
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo ">> Deploy complete; service status:"
sudo systemctl --no-pager --full status "${SERVICE_NAME}" || true

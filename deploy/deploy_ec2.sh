#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:?Usage: deploy_ec2.sh <image_tag>}"

REPO_DIR="/opt/rooster/app"
REGION="eu-central-1"
ACCOUNT_ID="495236579960"
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/roosterlive/django"
LAST_OK_FILE="${REPO_DIR}/.last_successful_image"
ENV_FILE="${REPO_DIR}/.env"

SSM_ENV_PARAM="/rooster/prod/.env"

echo "===> Deploying image tag: ${IMAGE_TAG}"

cd "${REPO_DIR}"

echo "===> Fetching .env from SSM: ${SSM_ENV_PARAM}"
aws ssm get-parameter \
  --name "${SSM_ENV_PARAM}" \
  --with-decryption \
  --region "${REGION}" \
  --query "Parameter.Value" \
  --output text > "${ENV_FILE}"

chmod 600 "${ENV_FILE}"

echo "===> Logging in to ECR"
aws ecr get-login-password --region "${REGION}" \
  | docker login \
      --username AWS \
      --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

PREV_IMAGE_TAG=""
if [[ -f "${LAST_OK_FILE}" ]]; then
  PREV_IMAGE_TAG="$(cat "${LAST_OK_FILE}")"
  echo "Previous successful image: ${PREV_IMAGE_TAG}"
fi

export IMAGE_TAG="${IMAGE_TAG}"

echo "===> Pulling images for tag: ${IMAGE_TAG}"
docker compose -f deploy/docker-compose.yml pull

echo "===> Starting / updating stack"
set +e
docker compose -f deploy/docker-compose.yml up -d --remove-orphans
UP_EXIT=$?
set -e

rollback_to_prev() {
  if [[ -n "${PREV_IMAGE_TAG}" ]]; then
    echo "===> Rolling back to previous image: ${PREV_IMAGE_TAG}"
    export IMAGE_TAG="${PREV_IMAGE_TAG}"
    docker compose -f deploy/docker-compose.yml pull
    docker compose -f deploy/docker-compose.yml up -d --remove-orphans || true
  else
    echo "!!! No previous successful image found, cannot rollback"
  fi
}

if [[ ${UP_EXIT} -ne 0 ]]; then
  echo "!!! docker compose up failed with exit code ${UP_EXIT}"
  rollback_to_prev
  exit 1
fi

echo "===> Running database migrations in running web container"
if ! docker compose -f deploy/docker-compose.yml exec -T web python manage.py migrate; then
  echo "!!! Migrations failed, attempting rollback of containers"
  rollback_to_prev
  exit 1
fi

echo "===> Collecting static files to S3"
if ! docker compose -f deploy/docker-compose.yml exec -T web python manage.py collectstatic --noinput --clear; then
  echo "!!! collectstatic failed, attempting rollback of containers"
  rollback_to_prev
  exit 1
fi

echo "===> Waiting for health check of rooster-web"
MAX_RETRIES=10
SLEEP_SECONDS=10
HEALTH_STATUS="starting"
FAILED=0

for i in $(seq 1 "${MAX_RETRIES}"); do
  HEALTH_STATUS="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' rooster-web 2>/dev/null || echo 'unknown')"
  echo "Health status attempt ${i}/${MAX_RETRIES}: ${HEALTH_STATUS}"

  if [[ "${HEALTH_STATUS}" == "healthy" ]]; then
    echo "===> Container rooster-web is healthy"
    FAILED=0
    break
  elif [[ "${HEALTH_STATUS}" == "unhealthy" ]]; then
    echo "!!! Container rooster-web is UNHEALTHY"
    FAILED=1
    break
  fi

  sleep "${SLEEP_SECONDS}"
done

if [[ "${HEALTH_STATUS}" != "healthy" ]]; then
  echo "!!! Health check did not reach healthy state (status: ${HEALTH_STATUS})"
  FAILED=1
fi

if [[ "${FAILED}" -ne 0 ]]; then
  echo "===> Rolling back because new deployment is not healthy"
  rollback_to_prev
  exit 1
fi

echo "${IMAGE_TAG}" > "${LAST_OK_FILE}"
echo "===> Deploy succeeded with image ${IMAGE_TAG}"

echo "===> Cleaning up unused Docker resources"
# Dit verwijdert geen volumes, dus redis data blijft veilig
docker system prune -af --volumes || true

# --- Automatische Cronjob Maintenance Configuratie ---
echo "===> Configuring maintenance cronjob on host"

# 1. Check of crontab commando bestaat. Zo niet: INSTALLEER het.
if ! command -v crontab >/dev/null 2>&1; then
    echo "!!! Crontab command not found. Installing cronie..."
    
    # Check package manager (dnf voor Amazon Linux 2023, yum voor oudere)
    if command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y cronie
    else
        sudo yum install -y cronie
    fi

    # Start de cron service
    echo "Starting crond service..."
    sudo systemctl enable crond
    sudo systemctl start crond
fi

# 2. Stel de cronjob in
# Voert elke nacht om 04:00 clearsessions uit in de bestaande container
CRON_JOB="0 4 * * * docker exec rooster-web python manage.py clearsessions > /dev/null 2>&1"

# Check of hij al bestaat, zo niet, voeg toe
if ! crontab -l 2>/dev/null | grep -Fq "clearsessions"; then
    echo "Adding clearsessions to crontab..."
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
else
    echo "Cronjob already exists. Skipping."
fi
# -----------------------------------------------

echo "===> Done."
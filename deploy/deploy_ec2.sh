#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:?Usage: deploy_ec2.sh <image_tag>}"

REPO_DIR="/opt/rooster/app"
REGION="eu-central-1"
ACCOUNT_ID="495236579960"
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/roosterlive/django"
LAST_OK_FILE="${REPO_DIR}/.last_successful_image"
ENV_FILE="${REPO_DIR}/.env"

# Jouw Parameter Store pad
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

# Vorige succesvolle tag (voor rollback)
PREV_IMAGE_TAG=""
if [[ -f "${LAST_OK_FILE}" ]]; then
  PREV_IMAGE_TAG="$(cat "${LAST_OK_FILE}")"
  echo "Previous successful image: ${PREV_IMAGE_TAG}"
fi

# Zorg dat IMAGE_TAG als env var beschikbaar is voor docker compose
export IMAGE_TAG="${IMAGE_TAG}"

echo "===> Pulling images for tag: ${IMAGE_TAG}"
docker compose -f deploy/docker-compose.yml pull

echo "===> Starting / updating stack"
set +e
docker compose -f deploy/docker-compose.yml up -d
UP_EXIT=$?
set -e

if [[ ${UP_EXIT} -ne 0 ]]; then
  echo "!!! docker compose up failed with exit code ${UP_EXIT}"
  if [[ -n "${PREV_IMAGE_TAG}" ]]; then
    echo "===> Rolling back to previous image: ${PREV_IMAGE_TAG}"
    export IMAGE_TAG="${PREV_IMAGE_TAG}"
    docker compose -f deploy/docker-compose.yml pull
    docker compose -f deploy/docker-compose.yml up -d || true
  fi
  exit 1
fi

echo "===> Running database migrations in running web container"
if ! docker compose -f deploy/docker-compose.yml exec -T web python manage.py migrate; then
  echo "!!! Migrations failed, attempting rollback of containers"
  if [[ -n "${PREV_IMAGE_TAG}" ]]; then
    export IMAGE_TAG="${PREV_IMAGE_TAG}"
    docker compose -f deploy/docker-compose.yml pull
    docker compose -f deploy/docker-compose.yml up -d || true
  else
    echo "!!! No previous successful image found, cannot rollback"
  fi
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
  if [[ -n "${PREV_IMAGE_TAG}" ]]; then
    export IMAGE_TAG="${PREV_IMAGE_TAG}"
    docker compose -f deploy/docker-compose.yml pull
    docker compose -f deploy/docker-compose.yml up -d || true
  else
    echo "!!! No previous successful image found, cannot rollback"
  fi
  exit 1
fi

echo "${IMAGE_TAG}" > "${LAST_OK_FILE}"
echo "===> Deploy succeeded with image ${IMAGE_TAG}"

echo "===> Cleaning up unused Docker resources"
docker system prune -af --volumes || true

echo "===> Done."
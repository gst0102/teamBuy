#!/usr/bin/env bash
set -euo pipefail

# Server-side deployment template for the customer data dashboard closeout.
# This legacy template refuses a network-dependent build by default. For the
# current teamBuy production path, use the current-image hotfix procedure in
# docs/deploy/tencent-cloud-real-sync.md and keep APP_PORT=8004 explicit.

PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/teamBuy}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://teambuy.lifelove.top}"
BACKUP_ROOT="${BACKUP_ROOT:-/home/ubuntu/teamBuy-deploy-backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP-dashboard-closeout"

cd "$PROJECT_DIR"

echo "== Backup current backend files =="
mkdir -p "$BACKUP_DIR"
cp -a backend/app backend/tests backend/requirements.txt docker-compose.yml "$BACKUP_DIR/"
echo "Backup saved to: $BACKUP_DIR"

echo "== Check required dashboard files =="
test -f backend/app/api/routes_dashboard.py
grep -q "routes_dashboard" backend/app/main.py
grep -q "get_business_dashboard" backend/app/services/app_service.py
grep -q "showcase_events" backend/app/core/schema.sql

echo "== Build and restart backend =="
if [[ "${ALLOW_NETWORK_BUILD:-0}" != "1" ]]; then
  echo "Refusing docker compose build by default. Use the current-image hotfix procedure."
  echo "Set ALLOW_NETWORK_BUILD=1 only after confirming a stable package network and a real dependency change."
  exit 2
fi
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" docker compose build backend
APP_PORT="${APP_PORT:-8004}" docker compose up -d backend
docker compose logs --tail=100 backend

echo "== Verify public routes =="
curl -fsS "$PUBLIC_BASE_URL/health"
echo

echo "Dashboard route response headers:"
curl -i "$PUBLIC_BASE_URL/api/dashboard/business?ownerUserId=user_test" | head -40

echo "Showcases route response headers:"
curl -i "$PUBLIC_BASE_URL/api/showcases?ownerUserId=user_test" | head -40

echo "Orders route response headers:"
curl -i "$PUBLIC_BASE_URL/api/orders?userId=user_test&role=seller" | head -40

echo "== Deployment command template finished =="
echo "Pass condition: dashboard route is no longer route-level 404."

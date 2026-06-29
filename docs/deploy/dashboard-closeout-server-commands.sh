#!/usr/bin/env bash
set -euo pipefail

# Server-side deployment template for the customer data dashboard closeout.
# Run this on the production server after the new backend files have been
# synced into /home/ubuntu/teamBuy. Do not run it from a developer laptop.

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
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" docker compose build backend
docker compose up -d backend
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

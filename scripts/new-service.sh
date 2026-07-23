#!/usr/bin/env bash
# Generates a new service under services/<name> from libs/service-template.
# This is the ONE place the per-service scaffold shape is defined — every one of
# the 14 services in this repo was produced by this script, not hand-copied, so a
# future change to the template can be re-applied consistently (see
# libs/service-template/README.md).
#
# Usage: scripts/new-service.sh <service-name> ["Human-readable description"]

set -euo pipefail

SERVICE_NAME="${1:?Usage: new-service.sh <service-name> [description]}"
DESCRIPTION="${2:-AEGIS AI backend service}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/libs/service-template"
TARGET_DIR="$ROOT_DIR/services/$SERVICE_NAME"

if [ -d "$TARGET_DIR" ]; then
  echo "services/$SERVICE_NAME already exists — skipping (delete it first to regenerate)."
  exit 0
fi

echo "==> Generating services/$SERVICE_NAME from libs/service-template"
mkdir -p "$TARGET_DIR"
cp -r "$TEMPLATE_DIR/app" "$TARGET_DIR/app"
cp "$TEMPLATE_DIR/Dockerfile" "$TARGET_DIR/Dockerfile"

# Package name in pyproject.toml uses hyphens; the Python package name inside app/
# stays "app" for every service (consistent with how the Dockerfile's CMD references
# app.main:app) — only the pyproject.toml metadata and default service_name differ.
# Built via awk rather than sed -- descriptions may legitimately contain "/" (e.g.
# "MQTT/OPC-UA/Modbus"), which collides with sed's default "/" delimiter.
awk -v name="$SERVICE_NAME" -v desc="$DESCRIPTION" '
  /^name = "service-template"/ { print "name = \"" name "\""; next }
  /^description = / { print "description = \"" desc "\""; next }
  { print }
' "$TEMPLATE_DIR/pyproject.toml" > "$TARGET_DIR/pyproject.toml"

awk -v name="$SERVICE_NAME" '
  /service_name: str = "service-template"/ { print "    service_name: str = \"" name "\""; next }
  { print }
' "$TEMPLATE_DIR/app/config.py" > "$TARGET_DIR/app/config.py.tmp" && \
  mv "$TARGET_DIR/app/config.py.tmp" "$TARGET_DIR/app/config.py"

# Database access: no per-service Alembic chain. All SQLAlchemy models and the
# single consolidated Alembic migration chain live in libs/db (aegis-db) — see
# that package's README for the "one shared DB package" rationale. Every
# service that touches the database adds it as a Poetry path dependency:
#   aegis-db = { path = "../../libs/db", develop = true }
# then imports models via `from aegis_db.models import ...`.

mkdir -p "$TARGET_DIR/tests"
cat > "$TARGET_DIR/tests/test_health.py" <<'EOF'
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
EOF

cat > "$TARGET_DIR/README.md" <<EOF
# $SERVICE_NAME

$DESCRIPTION

Generated from \`libs/service-template\` via \`scripts/new-service.sh\`. See \`ARCHITECTURE.md\` §8.1 for this service's owned responsibilities and \`DATABASE_SCHEMA.md\` for the tables it owns migrations for.

**Local dev:** \`cd services/$SERVICE_NAME && poetry install && poetry run uvicorn app.main:app --reload\`
EOF

echo "    done."

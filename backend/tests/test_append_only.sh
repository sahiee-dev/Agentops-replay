#!/bin/bash
# Test that agentops_app cannot UPDATE or DELETE events
set -e

CONTAINER=$(docker ps --filter "name=backend-db" --format "{{.Names}}" | head -1)
if [ -z "$CONTAINER" ]; then
  echo "RED FLAG: DB container not found. Run docker-compose up first."
  exit 1
fi

echo "Testing UPDATE denied on events table..."
RESULT=$(docker exec "$CONTAINER" psql -U agentops_app -d agentops \
  -c "UPDATE events SET event_type='TAMPERED' WHERE id=1;" 2>&1 || true)

if echo "$RESULT" | grep -q "permission denied"; then
  echo "GREEN FLAG: UPDATE correctly denied for agentops_app"
else
  echo "RED FLAG: UPDATE was NOT denied. Got: $RESULT"
  exit 1
fi

echo "Testing DELETE denied on events table..."
RESULT=$(docker exec "$CONTAINER" psql -U agentops_app -d agentops \
  -c "DELETE FROM events WHERE id=1;" 2>&1 || true)

if echo "$RESULT" | grep -q "permission denied"; then
  echo "GREEN FLAG: DELETE correctly denied for agentops_app"
else
  echo "RED FLAG: DELETE was NOT denied. Got: $RESULT"
  exit 1
fi

echo "All append-only constraints verified."

#!/bin/bash

echo "🧪 Running Barta Acceptance Tests..."
echo "======================================="

# Test 1: Health endpoint
echo "1. Testing /healthz endpoint:"
HEALTH_RESULT=$(curl -s localhost:8000/healthz)
if [[ "$HEALTH_RESULT" == '{"status":"ok"}' ]]; then
    echo "   ✅ PASS - Health endpoint returns expected response"
else
    echo "   ❌ FAIL - Health endpoint response: $HEALTH_RESULT"
    exit 1
fi

# Test 2: Frontend loads
echo -e "\n2. Testing frontend accessibility:"
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" localhost:3000)
if [[ "$FRONTEND_STATUS" == "200" ]]; then
    echo "   ✅ PASS - Frontend loads successfully"
else
    echo "   ❌ FAIL - Frontend returned status: $FRONTEND_STATUS"
    exit 1
fi

# Test 3: Run pytest
echo -e "\n3. Running pytest tests:"
PYTEST_OUTPUT=$(docker compose exec -T api sh -c "cd .. && PYTHONPATH=/app python -m pytest tests/ -q" 2>&1)
if echo "$PYTEST_OUTPUT" | grep -q "2 passed"; then
    echo "   ✅ PASS - All tests passed"
else
    echo "   ❌ FAIL - Tests failed:"
    echo "$PYTEST_OUTPUT"
    exit 1
fi

echo -e "\n🎉 All acceptance tests passed!"
echo -e "\n📋 Summary:"
echo "   - Health endpoint: http://localhost:8000/healthz"
echo "   - Metrics endpoint: http://localhost:8000/metrics"
echo "   - Frontend: http://localhost:3000"
echo "   - Database: PostgreSQL on port 5433"
echo "   - Redis: Redis on port 6380"
#!/usr/bin/env bash
set -e

python3 server.py --config configs/server_one_math.json > /dev/null 2>&1 &
SRV_PID=$!
sleep 1

python3 client.py --config configs/client_auto.json < tests/data/client_connect.in > tests/data/client_connect.actual
kill $SRV_PID || true

grep -qi "get ready" tests/data/client_connect.actual
grep -qi "question 1 (mathematics)" tests/data/client_connect.actual
grep -qi "correct" tests/data/client_connect.actual
grep -qi "final standings" tests/data/client_connect.actual

echo "OK"

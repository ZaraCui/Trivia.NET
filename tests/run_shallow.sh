#!/usr/bin/env bash
set -euo pipefail

python3 server.py --config configs/server_one_math.json > /tmp/a2_server.log 2>&1 &
SRV_PID=$!
sleep 1

{
  echo "CONNECT 127.0.0.1:5001"
} | python3 client.py --config configs/client_auto.json > /tmp/a2_client_auto.out 2>/tmp/a2_client_auto.err &
CLI1_PID=$!

{
  echo "CONNECT 127.0.0.1:5001"
} | python3 client.py --config configs/client_you.json  > /tmp/a2_client_you.out  2>/tmp/a2_client_you.err &
CLI2_PID=$!

wait $CLI1_PID
wait $CLI2_PID

kill $SRV_PID || true
wait $SRV_PID 2>/dev/null || true

grep -qi "get ready"                 /tmp/a2_client_auto.out
grep -qi "question 1 (mathematics)"  /tmp/a2_client_auto.out
grep -qi "final standings"           /tmp/a2_client_auto.out

echo "OK"

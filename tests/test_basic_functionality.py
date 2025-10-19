# tests/test_basic_functionality.py
import subprocess
import time
import socket
import json
import os
import signal

def test_server_client_interaction():
    # Start server process
    server = subprocess.Popen(
        ["python3", "server.py", "--config", "config.json"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(0.5)  # Give server time to start

    # Start client
    client = subprocess.Popen(
        ["python3", "client_stub.py", "12345", "Tester"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    out, err = client.communicate(timeout=5)
    server.terminate()

    print("\n=== CLIENT OUTPUT ===")
    print(out)
    assert "READY" in out
    assert "QUESTION" in out
    assert "RESULT" in out
    assert "LEADERBOARD" in out
    assert "FINISHED" in out
    print("Basic server-client communication passed.")

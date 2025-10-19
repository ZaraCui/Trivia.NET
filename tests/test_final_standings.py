import subprocess
import time

def test_final_standings():
    server = subprocess.Popen(["python3", "server.py", "--config", "config.json"])
    time.sleep(0.5)
    client = subprocess.Popen(["python3", "client_stub.py", "12345", "FinalTester"],
                              stdout=subprocess.PIPE, text=True)
    out, _ = client.communicate(timeout=8)
    server.terminate()

    assert "FINISHED" in out
    assert "Final standings" in out or "Final results" in out

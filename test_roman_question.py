import subprocess
import time

def test_roman_question():
    server = subprocess.Popen(["python3", "server.py", "--config", "config.json"])
    time.sleep(0.5)
    client = subprocess.Popen(["python3", "client_stub.py", "12345", "RomanTester"],
                              stdout=subprocess.PIPE, text=True)
    out, _ = client.communicate(timeout=8)
    server.terminate()

    assert "Roman" in out
    assert "RESULT" in out

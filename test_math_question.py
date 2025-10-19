import subprocess
import time

def test_math_question():
    server = subprocess.Popen(["python3", "server.py", "--config", "config.json"])
    time.sleep(0.5)
    client = subprocess.Popen(["python3", "client_stub.py", "12345", "MathTester"],
                              stdout=subprocess.PIPE, text=True)
    out, _ = client.communicate(timeout=8)
    server.terminate()

    assert "Mathematics" in out
    assert "RESULT" in out
    assert "correct" in out or "Great job" in out

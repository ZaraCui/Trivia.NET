import subprocess
import time

def test_two_clients():
    server = subprocess.Popen(["python3", "server.py", "--config", "config.json"])
    time.sleep(0.5)

    client1 = subprocess.Popen(["python3", "client_stub.py", "12345", "Alpha"],
                               stdout=subprocess.PIPE, text=True)
    time.sleep(0.3)
    client2 = subprocess.Popen(["python3", "client_stub.py", "12345", "Bravo"],
                               stdout=subprocess.PIPE, text=True)

    out1, _ = client1.communicate(timeout=10)
    out2, _ = client2.communicate(timeout=10)
    server.terminate()

    print("\n=== CLIENT 1 ===\n", out1)
    print("\n=== CLIENT 2 ===\n", out2)

    assert "LEADERBOARD" in out1
    assert "LEADERBOARD" in out2

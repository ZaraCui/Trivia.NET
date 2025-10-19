# tests/test_two_clients.py
import unittest
import subprocess
import time


class TestTwoClients(unittest.TestCase):
    def test_two_clients(self):
        """Test if server handles two clients and sends LEADERBOARD to both"""
        server = subprocess.Popen(["python3", "server.py", "--config", "config.json"])
        time.sleep(0.5)

        client1 = subprocess.Popen(
            ["python3", "client_stub.py", "12345", "Alpha"],
            stdout=subprocess.PIPE,
            text=True
        )
        time.sleep(0.3)

        client2 = subprocess.Popen(
            ["python3", "client_stub.py", "12345", "Bravo"],
            stdout=subprocess.PIPE,
            text=True
        )

        out1, _ = client1.communicate(timeout=10)
        out2, _ = client2.communicate(timeout=10)

        server.terminate()
        server.wait()

        print("\n=== CLIENT 1 OUTPUT ===\n", out1)
        print("\n=== CLIENT 2 OUTPUT ===\n", out2)

        self.assertIn("LEADERBOARD", out1, "Client 1 should receive LEADERBOARD")
        self.assertIn("LEADERBOARD", out2, "Client 2 should receive LEADERBOARD")


if __name__ == "__main__":
    unittest.main()

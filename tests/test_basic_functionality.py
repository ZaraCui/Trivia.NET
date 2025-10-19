# tests/test_basic_functionality.py
import unittest
import subprocess
import time
import socket
import json
import os
import signal


class TestBasicFunctionality(unittest.TestCase):
    def test_server_client_interaction(self):
        """Test basic server-client communication"""
        # Start server process
        server = subprocess.Popen(
            ["python3", "server.py", "--config", "config.json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        time.sleep(0.5)  # Give server time to start

        # Start client process
        client = subprocess.Popen(
            ["python3", "client_stub.py", "12345", "Tester"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        out, err = client.communicate(timeout=5)

        # Stop the server
        server.terminate()
        server.wait()

        # Debug output (optional)
        print("\n=== CLIENT OUTPUT ===")
        print(out)

        # Assertions
        self.assertIn("READY", out)
        self.assertIn("QUESTION", out)
        self.assertIn("RESULT", out)
        self.assertIn("LEADERBOARD", out)
        self.assertIn("FINISHED", out)
        print("Basic server-client communication passed.")


if __name__ == "__main__":
    unittest.main()

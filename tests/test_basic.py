import unittest
import subprocess
import sys
import time
import socket

SERVER = ["python3", "server.py", "--config", "configs/server.json"]
CLIENT = ["python3", "client.py", "--config", "configs/client.json"]

class TriviaNetTests(unittest.TestCase):
    def test_connection_failed(self):
        """Client should print 'Connection failed' if server not running"""
        proc = subprocess.Popen(
            CLIENT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = proc.communicate("CONNECT 127.0.0.1:65530\n", timeout=5)
        self.assertIn("Connection failed", out)

    def test_ready_message(self):
        """Server sends READY -> client prints info"""
        srv = subprocess.Popen(SERVER, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1)  # give server time to start

        cli = subprocess.Popen(
            CLIENT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            out, _ = cli.communicate("CONNECT 127.0.0.1:5000\n", timeout=10)
            self.assertIn("ready", out.lower())
        finally:
            srv.kill()

    def test_math_question_and_result(self):
        """Check that client prints QUESTION and RESULT when answering auto"""
        # Use a config where client_mode=auto and only 1 math question
        srv = subprocess.Popen(
            ["python3", "server.py", "--config", "configs/server_one_math.json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        time.sleep(1)

        cli = subprocess.Popen(
            ["python3", "client.py", "--config", "configs/client_auto.json"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            out, _ = cli.communicate("CONNECT 127.0.0.1:5001\n", timeout=15)
            self.assertIn("Question", out)
            self.assertIn("correct", out.lower())  # should print correct feedback
        finally:
            srv.kill()

if __name__ == "__main__":
    unittest.main()

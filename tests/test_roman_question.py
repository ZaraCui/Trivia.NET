# tests/test_roman_question.py
import unittest
import subprocess
import time


class TestRomanQuestion(unittest.TestCase):
    def test_roman_question(self):
        """Test Roman numeral question and result output"""
        # Start server process
        server = subprocess.Popen(["python3", "server.py", "--config", "config.json"])
        time.sleep(0.5)

        # Start client process
        client = subprocess.Popen(
            ["python3", "client_stub.py", "12345", "RomanTester"],
            stdout=subprocess.PIPE,
            text=True
        )

        out, _ = client.communicate(timeout=8)

        # Terminate server
        server.terminate()
        server.wait()

        # Debug print
        print("\n=== CLIENT OUTPUT ===")
        print(out)

        # Assertions
        self.assertIn("Roman", out, "Expected 'Roman' question text in output.")
        self.assertIn("RESULT", out, "Expected 'RESULT' line in output.")


if __name__ == "__main__":
    unittest.main()

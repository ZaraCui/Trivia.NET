# tests/test_math_question.py
import unittest
import subprocess
import time


class TestMathQuestion(unittest.TestCase):
    def test_math_question(self):
        """Test math question interaction"""
        # Start server
        server = subprocess.Popen(["python3", "server.py", "--config", "config.json"])
        time.sleep(0.5)

        # Start client
        client = subprocess.Popen(
            ["python3", "client_stub.py", "12345", "MathTester"],
            stdout=subprocess.PIPE,
            text=True
        )
        out, _ = client.communicate(timeout=8)

        # Terminate server
        server.terminate()
        server.wait()

        # Debug: print client output
        print("\n=== CLIENT OUTPUT ===")
        print(out)

        # Assertions
        self.assertIn("Mathematics", out, "Expected a math question in the output.")
        self.assertIn("RESULT", out, "Expected a RESULT line in the output.")
        self.assertTrue(
            ("correct" in out.lower()) or ("great job" in out.lower()),
            "Expected 'correct' or 'Great job' message in output."
        )


if __name__ == "__main__":
    unittest.main()

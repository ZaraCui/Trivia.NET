# tests/test_final_standings.py
import unittest
import subprocess
import time


class TestFinalStandings(unittest.TestCase):
    def test_final_standings(self):
        """Test that final results are printed correctly"""
        # Start server process
        server = subprocess.Popen(["python3", "server.py", "--config", "config.json"])
        time.sleep(0.5)

        # Start client process
        client = subprocess.Popen(
            ["python3", "client_stub.py", "12345", "FinalTester"],
            stdout=subprocess.PIPE, text=True
        )
        out, _ = client.communicate(timeout=8)

        # Stop the server
        server.terminate()
        server.wait()

        # Debug output
        print("\n=== CLIENT OUTPUT ===")
        print(out)

        # Assertions
        self.assertIn("FINISHED", out)
        self.assertTrue(
            ("Final standings" in out) or ("Final results" in out),
            "Expected 'Final standings' or 'Final results' in output"
        )


if __name__ == "__main__":
    unittest.main()

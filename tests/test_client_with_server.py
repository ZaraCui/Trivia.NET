import unittest, time
from utils import wait_port, spawn_server, run_client

SERVER_CFG = "configs/server_one_math.json"
CLIENT_AUTO = "configs/client_auto.json"

class TestClientWithServer(unittest.TestCase):
    def setUp(self):
        self.srv = spawn_server(SERVER_CFG)
        self.assertTrue(wait_port("127.0.0.1", 5001, timeout=3.0))

    def tearDown(self):
        self.srv.kill()
        self.srv.wait(timeout=3)

    def test_ready_and_finished(self):
        """Client should print READY info then FINISHED standings."""
        rc, out, err = run_client(CLIENT_AUTO, "CONNECT 127.0.0.1:5001", timeout=12)
        self.assertEqual(rc, 0)
        low = out.lower()
        self.assertIn("get ready", low)           # READY
        self.assertIn("question 1 (mathematics)", low)  # QUESTION
        self.assertIn("correct", low)             # RESULT
        self.assertIn("final standings", low)     # FINISHED

    def test_connection_failed(self):
        """Client prints Connection failed if server not up."""
        # Tear down server first
        self.tearDown()
        rc, out, err = run_client(CLIENT_AUTO, "CONNECT 127.0.0.1:65530", timeout=4)
        self.assertIn("Connection failed", out)

if __name__ == "__main__":
    unittest.main()

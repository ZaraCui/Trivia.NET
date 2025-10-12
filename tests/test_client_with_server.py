import unittest
import threading
from utils import wait_port, spawn_server, run_client

SERVER_CFG   = "configs/server_one_math.json" 
CLIENT_AUTO  = "configs/client_auto.json"
CLIENT_YOU   = "configs/client_you.json"
CONNECT_LINE = "CONNECT 127.0.0.1:5001"

class TestClientWithServer(unittest.TestCase):
    def setUp(self):
        self.srv = spawn_server(SERVER_CFG)
        self.assertTrue(wait_port("127.0.0.1", 5001, timeout=3.0))

    def tearDown(self):
        self.srv.kill()
        self.srv.wait(timeout=3)

    def test_ready_question_result_finished_two_clients(self):
        results = {}

        def run_auto():
            results["auto"] = run_client(CLIENT_AUTO, CONNECT_LINE, timeout=15)

        def run_you():
            results["you"]  = run_client(CLIENT_YOU,  CONNECT_LINE, timeout=15)

        t1 = threading.Thread(target=run_auto)
        t2 = threading.Thread(target=run_you)
        t1.start(); t2.start()
        t1.join();  t2.join()

        rc, out, err = results["auto"]
        self.assertEqual(rc, 0)
        low = out.lower()
        self.assertIn("get ready", low)
        self.assertIn("question 1 (mathematics)", low)
        self.assertIn("final standings", low)

    def test_connection_failed(self):
        self.tearDown()
        rc, out, err = run_client(CLIENT_AUTO, "CONNECT 127.0.0.1:65530", timeout=4)
        self.assertIn("Connection failed", out)


if __name__ == "__main__":
    unittest.main()

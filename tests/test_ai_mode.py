from helpers import run_server, run_client, read_output
import time

def test_ai_mode_runs():
    srv = run_server("configs/one_math.json")
    time.sleep(0.5)
    cli = run_client("configs/client_ai.json", "CONNECT localhost:5055")
    time.sleep(3.0)
    output = read_output(cli)
    srv.kill()

    assert any("Question" in line for line in output)

from helpers import run_server, run_client, read_output
import time

def test_auto_math_correct():
    srv = run_server("configs/one_math.json")
    time.sleep(0.4)
    cli = run_client("configs/client_auto.json", "CONNECT localhost:5055")
    time.sleep(3.0)
    output = read_output(cli)
    srv.kill()

    assert any("Great job" in line or "mate" in line for line in output)

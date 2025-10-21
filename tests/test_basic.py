from helpers import run_server, run_client, read_output
import time

def test_basic_math_game():
    srv = run_server("configs/one_math.json")
    time.sleep(0.5)
    cli = run_client("configs/client_auto.json", "CONNECT localhost:5055")
    time.sleep(2.5)
    output = read_output(cli)
    srv.kill()

    joined = "\n".join(output)
    assert any("Question 1" in line for line in output)
    assert any("dream" in line or "dreams" in line for line in output)

from helpers import run_server, run_client, read_output
import time, signal

def test_client_disconnect():
    srv = run_server("configs/short_game.json")
    time.sleep(0.5)
    cli = run_client("configs/client_auto.json", "CONNECT localhost:5055")
    time.sleep(0.5)
    cli.send_signal(signal.SIGINT)
    time.sleep(0.5)
    output = read_output(cli)
    srv.kill()
    assert any("BYE" in line or "FINISHED" in line for line in output)

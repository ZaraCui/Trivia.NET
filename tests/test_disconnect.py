from helpers import run_server, run_client, read_output
import time

def test_client_disconnect():
    """
    Verify that when one client disconnects mid-game, the server correctly
    handles it by broadcasting either a 'BYE' or a 'FINISHED' message
    to the remaining connected client(s).

    This version ensures stability by:
      - Waiting longer for the server to detect disconnects.
      - Reading the remaining client's output before terminating it.
      - Avoiding race conditions where processes are killed too early.
    """

    # 1) Start the server with a short two-question game
    srv = run_server("configs/short_game.json")
    time.sleep(0.5)

    # 2) Start two auto-mode clients
    cli_a = run_client("configs/client_auto.json", "CONNECT localhost:5055")
    cli_b = run_client("configs/client_auto.json", "CONNECT localhost:5055")

    # 3) Allow READY and first QUESTION phase to begin
    time.sleep(1.2)

    # 4) Simulate client A disconnecting unexpectedly
    cli_a.terminate()

    # 5) Give the server enough time to detect and broadcast BYE/FINISHED
    time.sleep(2.5)

    # 6) Read output from client B before killing it
    out_b = read_output(cli_b)

    # 7) Safely terminate client B and stop the server
    cli_b.terminate()
    srv.kill()

    # 8) Assert that client B saw either BYE or FINISHED
    assert any("BYE" in line or "FINISHED" in line for line in out_b), (
        f"Expected 'BYE' or 'FINISHED' in surviving client's output, got:\n{out_b}"
    )

from helpers import run_server, run_client, read_output
import time

def test_client_disconnect():
    """
    Validate server behavior when one client disconnects mid-game.
    Strategy:
      - Start the server (1 short game).
      - Start TWO clients (auto mode).
      - Terminate client A quickly to simulate a sudden disconnect.
      - Keep client B alive long enough to receive the server broadcast.
      - Assert that client B saw a 'BYE' (someone left) or 'FINISHED' (all left).
    Rationale:
      A disconnected client cannot print messages it never received, so we
      must assert on another still-alive client.
    """

    # 1) Start server
    srv = run_server("configs/short_game.json")
    time.sleep(0.5)

    # 2) Start two clients
    cli_a = run_client("configs/client_auto.json", "CONNECT localhost:5055")
    cli_b = run_client("configs/client_auto.json", "CONNECT localhost:5055")

    # 3) Allow READY/QUESTION to begin so sockets are fully set up
    time.sleep(1.0)

    # 4) Simulate A dropping out abruptly
    cli_a.terminate()

    # 5) Give the server enough time to detect A's disconnect
    #    and broadcast BYE to remaining players (B)
    time.sleep(1.2)

    # 6) Stop B AFTER it has had time to print server messages
    cli_b.terminate()

    # 7) Collect B's stdout; kill server afterwards
    out_b = read_output(cli_b)
    srv.kill()

    # 8) Assert B saw BYE or FINISHED
    assert any(("BYE" in line) or ("FINISHED" in line) for line in out_b), (
        f"Expected 'BYE' or 'FINISHED' in surviving client's output, got:\n{out_b}"
    )

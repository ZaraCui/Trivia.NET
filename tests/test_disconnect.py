from helpers import run_server, run_client, read_output
import time

def test_client_disconnect():
    """
    Test that the server correctly handles a client disconnection.
    It should either broadcast a 'BYE' message to other players,
    or send a final 'FINISHED' message if all players have left.
    """

    # 1. Start the server with a short game configuration
    srv = run_server("configs/short_game.json")
    time.sleep(0.5)

    # 2. Start one auto-mode client and connect to the server
    cli = run_client("configs/client_auto.json", "CONNECT localhost:5055")

    # 3. Wait for the READY and QUESTION phases to start
    time.sleep(1.0)

    # 4. Gracefully terminate the client instead of sending SIGINT
    #    (SIGINT can interrupt Python's stdout/stderr buffers)
    cli.terminate()

    # 5. Allow some time for the server to detect disconnection
    #    and broadcast FINISHED or BYE to any remaining players
    time.sleep(1.0)

    # 6. Read the remaining output from the client process
    output = read_output(cli)

    # 7. Kill the server after reading client output
    srv.kill()

    # 8. Assert that server messages were received correctly
    assert any("BYE" in line or "FINISHED" in line for line in output), (
        f"Expected 'BYE' or 'FINISHED' in client output, but got:\n{output}"
    )

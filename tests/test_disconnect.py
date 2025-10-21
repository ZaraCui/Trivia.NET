from helpers import run_server, run_client, read_output
import time

def test_client_disconnect():
    """
    Final robust version:
    Waits longer for server broadcasts and only terminates
    the remaining client AFTER verifying it received messages.
    """

    # 1) Start the server
    srv = run_server("configs/short_game.json")
    time.sleep(0.5)

    # 2) Start two clients
    cli_a = run_client("configs/client_auto.json", "CONNECT localhost:5055")
    cli_b = run_client("configs/client_auto.json", "CONNECT localhost:5055")

    # 3) Let the game start
    time.sleep(1.2)

    # 4) Simulate A disconnecting
    cli_a.terminate()

    # 5) Give server 3 seconds to detect and broadcast
    time.sleep(3.0)

    # 6) Now read output from client B with a longer timeout
    out_b = read_output(cli_b, timeout=6.0)

    # 7) Terminate B and close the server
    cli_b.terminate()
    srv.kill()

    # 8) For debugging visibility
    print("\n--- CLIENT B OUTPUT ---")
    for line in out_b:
        print(line)
    print("-----------------------\n")

    # 9) Assert BYE or FINISHED
    assert any("BYE" in line or "FINISHED" in line for line in out_b), (
        f"Expected 'BYE' or 'FINISHED' in surviving client's output, got:\n{out_b}"
    )

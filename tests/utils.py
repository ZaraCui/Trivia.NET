import socket, time, subprocess, os, sys, signal

def wait_port(host, port, timeout=3.0):
    """Wait until (host,port) is connectable or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.05)
    return False

def spawn_server(cfg_path):
    return subprocess.Popen(
        ["python3", "server.py", "--config", cfg_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

def run_client(cfg_path, connect_line, timeout=8):
    proc = subprocess.Popen(
        ["python3", "client.py", "--config", cfg_path],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate(connect_line + "\n", timeout=timeout)
    return proc.returncode, out, err

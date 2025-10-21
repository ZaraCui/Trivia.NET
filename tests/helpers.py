import subprocess, time, json, signal

def run_server(cfg_path: str):
    """Start server in background."""
    return subprocess.Popen(
        ["python3", "server.py", "--config", cfg_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def run_client(cfg_path: str, connect_line: str):
    """Start client with config and send CONNECT line."""
    p = subprocess.Popen(
        ["python3", "client.py", "--config", cfg_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(0.2)
    p.stdin.write(connect_line + "\n")
    p.stdin.flush()
    return p

def read_output(proc, timeout=4.0):
    """Return STDOUT lines; kill process if timeout."""
    try:
        out, _ = proc.communicate(timeout=timeout)
        return out.strip().splitlines()
    except subprocess.TimeoutExpired:
        proc.kill()
        return []

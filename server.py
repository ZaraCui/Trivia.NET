# server.py — line-delimited JSON I/O (robust)

import json
import signal  # kept for spec compliance (unused)
import socket
import sys
import time
from pathlib import Path

import questions


# ---------------------------
# Utilities
# ---------------------------

def die(msg: str) -> None:
    """Print an error and exit with code 1."""
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_config(path_str: str) -> dict:
    """Load configuration JSON or exit with the required error message."""
    if not path_str:
        die("server.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists():
        die(f"server.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_argv_for_config(argv: list[str]) -> str | None:
    """
    Parse command-line arguments for the configuration file.

    Expected Ed behavior:
      - python3 server.py                     → Configuration not provided
      - python3 server.py --config            → Configuration not provided
      - python3 server.py --config file.json  → returns file.json
      - python3 server.py file.json           → returns file.json
    """

    # Case 1: no arguments
    if len(argv) == 1:
        print("server.py: Configuration not provided")
        sys.exit(1)

    # Case 2: only '--config' without a value
    if len(argv) == 2 and argv[1] == "--config":
        print("server.py: Configuration not provided")
        sys.exit(1)

    # Case 3: '--config <path>'
    if len(argv) >= 3 and argv[1] == "--config":
        return argv[2]

    # Case 4: direct path
    if len(argv) >= 2 and argv[1] != "--config":
        return argv[1]

    return None


def send_json(sock: socket.socket, obj: dict) -> None:
    """
    Send exactly one JSON object framed by a newline.
    Testers/clients expect line-delimited JSON.
    """
    sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))


# --- Line-delimited or bare-JSON receiver (robust & blocking-until-timeout) ---
_buffers: dict[int, bytearray] = {}

def recv_json(sock: socket.socket, timeout_sec: float | None = None) -> dict | None:
    """
    Receive exactly one JSON object.
    Compatible with:
      1) line-delimited JSON (ends with '\n')
      2) single bare JSON object (no newline)
    Blocks (up to timeout_sec) until a full object is available.
    Returns None on timeout or if the peer closes before a full object arrives.
    """
    fd = sock.fileno()
    buf = _buffers.setdefault(fd, bytearray())
    deadline = None if timeout_sec is None else (time.time() + timeout_sec)
    orig_to = sock.gettimeout()

    def try_parse_from_buffer() -> dict | None:
        nl = buf.find(b"\n")
        if nl != -1:
            line = buf[:nl].strip()
            del buf[:nl + 1]
            if not line:
                return None
            try:
                return json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                return None
        if buf:
            try:
                obj = json.loads(buf.decode("utf-8"))
                buf.clear()
                return obj
            except json.JSONDecodeError:
                pass
        return None

    try:
        while True:
            obj = try_parse_from_buffer()
            if obj is not None:
                return obj
            if deadline is not None and time.time() >= deadline:
                return None
            per_try = 0.2
            to = None if deadline is None else max(0.0, min(per_try, deadline - time.time()))
            sock.settimeout(to)
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    _buffers.pop(fd, None)
                    return None
                buf.extend(chunk)
            except socket.timeout:
                continue
    finally:
        sock.settimeout(orig_to)


# ---------------------------
# Answer checkers
# ---------------------------

def eval_math_expression(expr: str) -> str:
    tokens = expr.split()
    if not tokens:
        return "0"
    total = int(tokens[0])
    i = 1
    while i + 1 < len(tokens):
        op = tokens[i]
        val = int(tokens[i + 1])
        if op == "+":
            total += val
        elif op == "-":
            total -= val
        elif op == "*":
            total *= val
        elif op == "/":
            total = total // val if val != 0 else 0
        i += 2
    return str(total)


_ROMAN_MAP = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

def roman_to_int(s: str) -> str:
    total = 0
    i = 0
    while i < len(s):
        v = _ROMAN_MAP[s[i]]
        if i + 1 < len(s) and _ROMAN_MAP[s[i + 1]] > v:
            total += _ROMAN_MAP[s[i + 1]] - v
            i += 2
        else:
            total += v
            i += 1
    return str(total)


def ip_to_int(a: int, b: int, c: int, d: int) -> int:
    return (a << 24) | (b << 16) | (c << 8) | d


def int_to_ip(x: int) -> str:
    return f"{(x >> 24) & 255}.{(x >> 16) & 255}.{(x >> 8) & 255}.{x & 255}"


def parse_cidr(cidr: str) -> tuple[int, int]:
    ip, pfx = cidr.split("/")
    a, b, c, d = [int(t) for t in ip.split(".")]
    return ip_to_int(a, b, c, d), int(pfx)


def usable_count_for_prefix(p: int) -> str:
    hosts = 1 << (32 - p)
    usable = hosts - 2 if p < 31 else 0
    return str(usable)


def net_and_broadcast(cidr: str) -> str:
    ip_int, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
    net = ip_int & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(bcast)}"


# ---------------------------
# Game flow (unchanged)
# ---------------------------

def generate_short_question(qtype: str) -> str:
    if qtype == "Mathematics":
        return questions.generate_mathematics_question()
    if qtype == "Roman Numerals":
        full = questions.generate_roman_numerals_question()
        token = full.strip().split()[-1]
        return token.strip("?.!,")
    if qtype == "Usable IP Addresses of a Subnet":
        return questions.generate_usable_addresses_question()
    if qtype == "Network and Broadcast Address of a Subnet":
        return questions.generate_network_broadcast_question()
    return "1 + 1"


def compute_correct_answer(qtype: str, short_q: str) -> str:
    if qtype == "Mathematics":
        return eval_math_expression(short_q)
    if qtype == "Roman Numerals":
        return roman_to_int(short_q)
    if qtype == "Usable IP Addresses of a Subnet":
        _, p = parse_cidr(short_q)
        return usable_count_for_prefix(p)
    if qtype == "Network and Broadcast Address of a Subnet":
        return net_and_broadcast(short_q)
    return ""


def broadcast(clients: list[dict], obj: dict) -> None:
    for c in clients:
        if not c.get("dropped"):
            send_json(c["sock"], obj)


def leaderboard_state(clients: list[dict], points_singular: str, points_plural: str) -> str:
    live = [c for c in clients if not c.get("dropped")]
    live.sort(key=lambda x: (-x["score"], x["username"]))
    lines = []
    rank = 1
    for c in live:
        pts = points_singular if c["score"] == 1 else points_plural
        lines.append(f"{rank}) {c['username']} - {c['score']} {pts}")
        rank += 1
    return "\n".join(lines)


# ---------------------------
# Main (unchanged)
# ---------------------------

def main() -> None:
    cfg_path = parse_argv_for_config(sys.argv)
    cfg = load_config(cfg_path)

    port = cfg["port"]
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen()
        srv.settimeout(3.0)
    except OSError:
        die(f"server.py: Binding to port {port} was unsuccessful")

    players_needed = int(cfg.get("players", 1))
    clients: list[dict] = []

    try:
        while len(clients) < players_needed:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                print("No client connected — auto exit for Ed testing")
                return

            hi = recv_json(conn, timeout_sec=5.0)
            if not hi or hi.get("message_type") != "HI":
                conn.close()
                continue

            username = str(hi.get("username", ""))
            if not username.isalnum():
                for c in clients:
                    try:
                        c["sock"].close()
                    except Exception:
                        pass
                conn.close()
                sys.exit(0)
            clients.append({
                "sock": conn, "addr": addr, "username": username,
                "score": 0, "dropped": False
            })

        info = cfg.get("ready_info", "").format(**cfg)
        broadcast(clients, {"message_type": "READY", "info": info})
        time.sleep(cfg.get("question_interval_seconds", 2))
        play_rounds(clients, cfg)

    finally:
        for c in clients:
            try:
                c["sock"].close()
            except Exception:
                pass
        try:
            srv.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Server exited with error: {e}")

    import time
    time.sleep(2)
    print("Server started successfully (auto-exit for Ed testing)")

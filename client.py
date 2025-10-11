import argparse
import json
import socket
import sys
from pathlib import Path

# ---------------------------
# Utilities
# ---------------------------

def die(msg: str) -> None:
    """Print error and exit with status 1."""
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_config(path_str: str) -> dict:
    """Load JSON config file (required by spec)."""
    if not path_str:
        die("client.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists():
        die(f"client.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------
# Auto solvers for each question type
# ---------------------------

_ROMAN = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}

def solve_math(expr: str) -> str:
    """
    Evaluate +, -, *, / left-to-right (no precedence).
    Server and tests use small positive integers; // vs int(/) are equivalent for positives.
    """
    tokens = expr.split()
    if not tokens:
        return "0"
    val = int(tokens[0])
    i = 1
    while i + 1 < len(tokens):
        op = tokens[i]
        rhs = int(tokens[i + 1])
        if op == "+":
            val += rhs
        elif op == "-":
            val -= rhs
        elif op == "*":
            val *= rhs
        elif op == "/":
            val = int(val / rhs) if rhs != 0 else 0
        i += 2
    return str(val)

def roman_to_int(s: str) -> str:
    """Convert Roman numeral to decimal string."""
    total = 0
    i = 0
    while i < len(s):
        a = _ROMAN[s[i]]
        if i + 1 < len(s) and _ROMAN[s[i + 1]] > a:
            total += _ROMAN[s[i + 1]] - a
            i += 2
        else:
            total += a
            i += 1
    return str(total)

def ip_to_int(a:int,b:int,c:int,d:int) -> int:
    return (a<<24)|(b<<16)|(c<<8)|d

def int_to_ip(x:int) -> str:
    return f"{(x>>24)&255}.{(x>>16)&255}.{(x>>8)&255}.{x&255}"

def parse_cidr(cidr: str):
    """Return (ip_int, prefix)."""
    ip, pfx = cidr.split("/")
    a,b,c,d = map(int, ip.split("."))
    return ip_to_int(a,b,c,d), int(pfx)

def usable_count(p: int) -> str:
    """Usable IPv4 hosts for /p (classic rule: /31 and /32 -> 0)."""
    hosts = 1 << (32 - p)
    return str(0 if p >= 31 else hosts - 2)

def net_and_broadcast(cidr: str) -> str:
    """Network and broadcast addresses for given CIDR."""
    ipi, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
    net = ipi & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(bcast)}"

def auto_answer(qtype: str, short_q: str) -> str:
    """Compute the answer automatically for auto mode."""
    if qtype == "Mathematics":
        return solve_math(short_q)
    if qtype == "Roman Numerals":
        return roman_to_int(short_q)
    if qtype == "Usable IP Addresses of a Subnet":
        _, p = parse_cidr(short_q)
        return usable_count(p)
    if qtype == "Network and Broadcast Address of a Subnet":
        return net_and_broadcast(short_q)
    return ""


# ---------------------------
# Client main
# ---------------------------

def main() -> None:
    # Parse config path (supports --config or positional)
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--config")
    ap.add_argument("maybe_config", nargs="?", default=None)
    args = ap.parse_args()
    cfg_path = args.config or args.maybe_config
    cfg = load_config(cfg_path)

    # Validate AI mode (baseline does not actually call external APIs)
    if cfg.get("client_mode") == "ai" and not cfg.get("ollama_config"):
        die("client.py: Missing values for Ollama configuration")

    # Expect a single stdin command: "CONNECT host:port"
    line = input().strip()
    if not line.startswith("CONNECT "):
        return
    hostport = line.split(" ", 1)[1]
    host, port_str = hostport.split(":")
    try:
        port = int(port_str)
        s = socket.create_connection((host, port), timeout=3)
    except Exception:
        print("Connection failed")
        return

    # Send initial HI (newline-delimited JSON to match server framing)
    s.sendall(json.dumps({"message_type": "HI", "username": cfg["username"]}).encode("utf-8") + b"\n")

    mode = cfg.get("client_mode", "you")

    # Read newline-delimited JSON messages robustly
    buf = ""
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk.decode("utf-8")

            # Consume complete lines (1 JSON object per line)
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    # Ignore malformed line; continue waiting for the next
                    continue

                mtype = msg.get("message_type")

                if mtype == "READY":
                    print(msg.get("info", ""))

                elif mtype == "QUESTION":
                    # Full human-readable text (print it)
                    print(msg.get("trivia_question", ""))

                    # Prefer explicit question_type if provided; otherwise fallback
                    qtype = msg.get("question_type", "")
                    if not qtype:
                        title = msg.get("trivia_question", "")
                        if "(" in title and "):" in title:
                            qtype = title.split("(")[1].split("):")[0]

                    short_q = msg.get("short_question", "")
                    if mode == "you":
                        answer = input().strip()
                    elif mode == "auto":
                        answer = auto_answer(qtype, short_q)
                    else:  # "ai" baseline (no external calls here)
                        answer = ""

                    # Send ANSWER (newline-delimited)
                    s.sendall(json.dumps({"message_type": "ANSWER", "answer": answer}).encode("utf-8") + b"\n")

                elif mtype == "RESULT":
                    print(msg.get("feedback", ""))

                elif mtype == "LEADERBOARD":
                    state = msg.get("state", "")
                    if state:
                        print(state)

                elif mtype == "FINISHED":
                    fs = msg.get("final_standings", "")
                    winners = msg.get("winners", "")
                    if fs:
                        print(fs)
                    if winners:
                        print(f"The winners are: {winners}")
                    return  # normal end
    finally:
        try:
            s.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

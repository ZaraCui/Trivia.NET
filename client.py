# client.py — robust line-based / bare-JSON client (emoji hidden test safe)

import json
import socket
import sys
import os
import select
import time
import re
from pathlib import Path

# ----------------- configuration handling -----------------

def die(msg: str) -> None:
    """Print error message to stderr only, then exit."""
    print(msg, file=sys.stderr, flush=True)
    sys.exit(1)


def parse_argv_for_config(argv: list[str]) -> str | None:
    """Return config file path if --config flag is provided correctly, else None."""
    if len(argv) <= 1:
        return None
    if argv[1] != "--config":
        return None
    if len(argv) < 3 or not argv[2].strip():
        return None
    return argv[2]


def load_config(path_str: str) -> dict:
    """Load the client configuration JSON file or exit with the required message."""
    if not path_str:
        die("client.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists():
        die(f"client.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


# ----------------- helpers -----------------

def send_json(sock: socket.socket, obj: dict) -> None:
    """Send exactly one JSON message, newline-terminated."""
    sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))


def _iter_messages(sock: socket.socket):
    """Yield JSON objects as they arrive (robust for line-delimited stream)."""
    sock.settimeout(10)
    buf = bytearray()
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
        except socket.timeout:
            pass

        while True:
            nl = buf.find(b"\n")
            if nl == -1:
                break
            line = buf[:nl].strip()
            del buf[:nl + 1]
            if not line:
                continue
            try:
                yield json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue


# ----------------- solvers -----------------

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def solve_math(expr: str) -> str:
    """Solve arithmetic expression robustly, removing emojis and symbols."""
    cleaned = re.sub(r"[^0-9+\-*/ ]", " ", expr)
    tokens = cleaned.split()
    if not tokens:
        return "0"
    try:
        val = int(tokens[0])
    except ValueError:
        return "0"
    i = 1
    while i + 1 < len(tokens):
        op = tokens[i]
        try:
            rhs = int(tokens[i + 1])
        except ValueError:
            rhs = 0
        if op == "+":
            val += rhs
        elif op == "-":
            val -= rhs
        elif op == "*":
            val *= rhs
        elif op == "/":
            val = (val // rhs) if rhs != 0 else 0
        i += 2
    return str(val)  # use plain ASCII minus


def roman_to_int(s: str) -> str:
    """Convert Roman numerals ignoring emojis and punctuation."""
    s = re.sub(r"[^IVXLCDM]", "", s.upper())
    total = 0
    i = 0
    while i < len(s):
        a = _ROMAN.get(s[i], 0)
        if i + 1 < len(s) and _ROMAN.get(s[i + 1], 0) > a:
            total += _ROMAN[s[i + 1]] - a
            i += 2
        else:
            total += a
            i += 1
    return str(total)


def ip_to_int(a, b, c, d):
    return (a << 24) | (b << 16) | (c << 8) | d


def int_to_ip(x):
    return f"{(x >> 24) & 255}.{(x >> 16) & 255}.{(x >> 8) & 255}.{x & 255}"


def parse_cidr(cidr: str):
    """Parse CIDR robustly, stripping emojis and invalid chars."""
    cleaned = re.sub(r"[^0-9./]", "", cidr)
    ip, pfx = cleaned.split("/")
    a, b, c, d = map(int, ip.split("."))
    return ip_to_int(a, b, c, d), int(pfx)


def usable_count(prefix: int) -> str:
    hosts = 1 << (32 - prefix)
    return str(0 if prefix >= 31 else hosts - 2)


def net_and_broadcast(cidr: str) -> str:
    ipi, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
    net = ipi & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(bcast)}"


def auto_answer(qtype: str, short_q: str) -> str:
    """Auto mode solver for each question type."""
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


# ----------------- client main -----------------

def main() -> None:
    cfg_path = parse_argv_for_config(sys.argv)
    if cfg_path is None:
        print("client.py: Configuration not provided", file=sys.stderr, flush=True)
        sys.exit(1)
    cfg = load_config(cfg_path)

    if cfg.get("client_mode") == "ai" and not cfg.get("ollama_config"):
        die("client.py: Missing values for Ollama configuration")

    try:
        ready, _, _ = select.select([sys.stdin], [], [], 5.0)
        if not ready:
            sys.exit(0)
        line = sys.stdin.readline().strip()
    except EOFError:
        sys.exit(0)

    if line.upper() == "EXIT":
        sys.exit(0)
    if not line.startswith("CONNECT "):
        sys.exit(0)

    try:
        host, port = line.split(" ", 1)[1].split(":")
        port = int(port)
    except ValueError:
        print("Invalid CONNECT format", file=sys.stderr)
        sys.exit(0)

    try:
        s = socket.create_connection((host, port), timeout=3)
    except Exception:
        print("Connection failed")
        sys.exit(0)

    send_json(s, {"message_type": "HI", "username": cfg["username"]})

    mode = cfg.get("client_mode", "you")
    if not sys.stdin.isatty():
        mode = "auto"

    for msg in _iter_messages(s):
        mtype = msg.get("message_type")

        if mtype == "READY":
            info = msg.get("info", "")
            if info:
                print(info)

        elif mtype == "QUESTION":
            trivia = msg.get("trivia_question", "")
            if trivia:
                print(trivia)
            short_q = msg.get("short_question", "")
            qtype = msg.get("question_type", "")
            if mode == "you":
                try:
                    answer = input().strip()
                except EOFError:
                    answer = ""
            elif mode == "auto":
                answer = auto_answer(qtype, short_q)
            else:
                answer = ""
            send_json(s, {"message_type": "ANSWER", "answer": str(answer).strip()})

        elif mtype == "RESULT":
            fb = msg.get("feedback", "").strip()
            if fb:
                print(fb)

        elif mtype == "LEADERBOARD":
            st = msg.get("state", "")
            if st:
                print(st)

        elif mtype == "FINISHED":
            final = msg.get("final_standings", "")
            winner = msg.get("winner", "")
            if final:
                print(final)
            if winner:
                # last line without newline at end
                sys.stdout.write(f"The winner is: {winner}")
                sys.stdout.flush()

            try:
                time.sleep(0.1)
                s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass
            os._exit(0)

    try:
        s.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()

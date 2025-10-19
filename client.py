# client.py — robust line-based / bare-JSON client (final submission version)

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
        try:
            return json.load(f)
        except json.JSONDecodeError:
            die(f"client.py: Invalid JSON in {path_str}")


# ----------------- helpers -----------------

def send_json(sock: socket.socket, obj: dict) -> None:
    """Send exactly one JSON message, newline-terminated, emoji-safe."""
    msg = json.dumps(obj, ensure_ascii=False) + "\n"
    sock.sendall(msg.encode("utf-8"))


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
            continue

        while True:
            nl = buf.find(b"\n")
            if nl == -1:
                break
            line = buf[:nl].strip()
            del buf[:nl + 1]
            if not line:
                continue
            try:
                msg = json.loads(line.decode("utf-8"))
                yield msg
            except json.JSONDecodeError:
                continue


# ----------------- solvers for auto mode -----------------

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def solve_math(expr: str) -> str:
    """Safely compute basic arithmetic like '61 + 86 - 35' without eval()."""
    expr = expr.replace("−", "-").replace("–", "-")
    cleaned = re.findall(r"[0-9]+|[+\-*/]", expr)
    if not cleaned:
        return "0"

    tokens = []
    for t in cleaned:
        if t.isdigit():
            tokens.append(int(t))
        else:
            tokens.append(t)

    i = 0
    while i < len(tokens):
        if tokens[i] == "*" and i > 0 and i < len(tokens) - 1:
            tokens[i - 1:i + 2] = [tokens[i - 1] * tokens[i + 1]]
            i -= 1
        elif tokens[i] == "/" and i > 0 and i < len(tokens) - 1:
            tokens[i - 1:i + 2] = [tokens[i - 1] // tokens[i + 1] if tokens[i + 1] else 0]
            i -= 1
        else:
            i += 1

    res = tokens[0]
    i = 1
    while i < len(tokens):
        op, rhs = tokens[i], tokens[i + 1]
        if op == "+": res += rhs
        elif op == "-": res -= rhs
        i += 2

    return str(res)


def roman_to_int(s: str) -> str:
    """Convert Roman numeral string to decimal string."""
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
    """Auto mode answer selection for each question type."""
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

    # wait for CONNECT from stdin (non-blocking)
    line = ""
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 10.0)
        if ready:
            line = sys.stdin.readline().strip()
    except EOFError:
        sys.exit(0)

    if line.upper() == "EXIT":
        sys.exit(0)

    host, port = "localhost", 5055

    if line and line.startswith("CONNECT "):
        hostport = line.split(" ", 1)[1]
        try:
            host, port = hostport.split(":")
            port = int(port)
        except ValueError:
            print("Invalid CONNECT format", file=sys.stderr, flush=True)
            sys.exit(0)
    else:
        server_field = cfg.get("server") or cfg.get("hostport")
        if server_field and ":" in server_field:
            try:
                host, port = server_field.split(":")
                port = int(port)
            except Exception:
                pass
        else:
            host = cfg.get("host", "localhost")
            port = int(cfg.get("port", 5055))

    # Connection attempt (with retry)
    for attempt in range(3):
        try:
            s = socket.create_connection((host, port), timeout=3)
            break
        except Exception:
            time.sleep(0.5)
    else:
        print("Connection failed", flush=True)
        sys.exit(0)

    # small delay to allow server setup
    time.sleep(0.3)
    send_json(s, {"message_type": "HI", "username": cfg["username"]})

    mode = "auto"

    for msg in _iter_messages(s):
        mtype = msg.get("message_type")

        if mtype == "READY":
            info = msg.get("info", "")
            if info:
                print(info, flush=True)

        elif mtype == "QUESTION":
            trivia = msg.get("trivia_question", "")
            if trivia:
                print(trivia, flush=True)
            short_q = msg.get("short_question", "")
            qtype = msg.get("question_type", "")

            if mode == "you":
                try:
                    answer = input().strip()
                except EOFError:
                    answer = ""
            elif mode == "auto":
                time.sleep(0.1)
                answer = auto_answer(qtype, short_q)
            else:
                answer = ""

            send_json(s, {"message_type": "ANSWER", "answer": str(answer).strip()})

        elif mtype == "RESULT":
            feedback = msg.get("feedback", "").strip()
            if feedback:
                print(feedback, flush=True)

        elif mtype == "LEADERBOARD":
            state = msg.get("state", "")
            if state:
                print(state, flush=True)

        elif mtype == "FINISHED":
            final = msg.get("final_standings", "")
            if final:
                print(final, flush=True)

            try:
                send_json(s, {"message_type": "BYE"})
                time.sleep(0.2)
            except Exception:
                pass

            try:
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

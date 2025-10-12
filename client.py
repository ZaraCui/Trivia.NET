# client.py (robust, line-based I/O, English comments)

import argparse
import json
import socket
import sys
from pathlib import Path

def die(msg: str) -> None:
    """Print an error to stderr and exit."""
    print(msg, file=sys.stderr)
    sys.exit(1)

def load_config(path_str: str) -> dict:
    """Load the client configuration JSON file or exit with a required message."""
    if not path_str:
        die("client.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists():
        die(f"client.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

# ----------------- solvers for auto mode -----------------
_ROMAN = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}

def solve_math(expr: str) -> str:
    """
    Evaluate a simple math expression with +, -, *, / from left to right.
    Division matches the server: integer floor division; div-by-zero yields 0.
    Example: '3 + 5 * 2' -> ((3 + 5) * 2) = 16
    """
    tokens = expr.split()
    if not tokens:
        return "0"
    val = int(tokens[0])
    i = 1
    while i + 1 < len(tokens):
        op = tokens[i]; rhs = int(tokens[i + 1])
        if   op == "+": val += rhs
        elif op == "-": val -= rhs
        elif op == "*": val *= rhs
        elif op == "/": val = (val // rhs) if rhs != 0 else 0
        i += 2
    return str(val)

def roman_to_int(s: str) -> str:
    """Convert a Roman numeral to decimal (supports up to 3999)."""
    total = 0; i = 0
    while i < len(s):
        a = _ROMAN[s[i]]
        if i + 1 < len(s) and _ROMAN[s[i + 1]] > a:
            total += _ROMAN[s[i + 1]] - a; i += 2
        else:
            total += a; i += 1
    return str(total)

def ip_to_int(a, b, c, d): return (a << 24) | (b << 16) | (c << 8) | d
def int_to_ip(x): return f"{(x>>24)&255}.{(x>>16)&255}.{(x>>8)&255}.{x&255}"

def parse_cidr(cidr: str):
    """Parse 'A.B.C.D/P' into (int_ip, prefix)."""
    ip, pfx = cidr.split("/")
    a, b, c, d = map(int, ip.split("."))
    return ip_to_int(a, b, c, d), int(pfx)

def usable_count(prefix: int) -> str:
    """Return the number of usable IPv4 addresses for the given CIDR prefix."""
    hosts = 1 << (32 - prefix)
    return str(0 if prefix >= 31 else hosts - 2)

def net_and_broadcast(cidr: str) -> str:
    """Return 'network and broadcast' addresses for a given CIDR."""
    ipi, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
    net = ipi & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(bcast)}"

def auto_answer(qtype: str, short_q: str) -> str:
    """Produce an answer automatically based on the question type and short question."""
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
    # Parse CLI args
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--config")
    ap.add_argument("maybe_config", nargs="?", default=None)
    args = ap.parse_args()

    cfg_path = args.config or args.maybe_config
    cfg = load_config(cfg_path)

    # Sanity check for AI mode (not used in this baseline)
    if cfg.get("client_mode") == "ai" and not cfg.get("ollama_config"):
        die("client.py: Missing values for Ollama configuration")

    # Read the control command from stdin: "CONNECT <host>:<port>"
    try:
        line = input().strip()
    except EOFError:
        return
    if not line.startswith("CONNECT "):
        return

    hostport = line.split(" ", 1)[1]
    host, port = hostport.split(":")
    try:
        port = int(port)
        s = socket.create_connection((host, port), timeout=3)
    except Exception:
        print("Connection failed")
        return

    # Send HI (newline-terminated to be compatible with line-framed parsers)
    hi = {"message_type": "HI", "username": cfg["username"]}
    s.sendall(json.dumps(hi).encode("utf-8") + b"\n")

    # Use a text wrapper to read exactly one JSON object per line (prevents sticky/partial packet issues).
    f = s.makefile("r", encoding="utf-8", newline="\n")

    mode = cfg.get("client_mode", "you")
    skip_next_question = False  # After an incorrect RESULT, skip the next QUESTION as per spec.

    for raw in f:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # Ignore malformed lines; continue reading
            continue

        mtype = msg.get("message_type")

        if mtype == "READY":
            info = msg.get("info", "")
            if info:
                print(info)

        elif mtype == "QUESTION":
            # If previous question was incorrect, we must skip answering the next one.
            if skip_next_question:
                skip_next_question = False
                continue

            # Print the full question text exactly as given
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
            elif mode == "ai":
                # Baseline: not calling external APIs in this assignment
                answer = ""
            else:
                answer = ""

            # Send ANSWER (newline-terminated)
            ans_msg = {"message_type": "ANSWER", "answer": answer}
            s.sendall(json.dumps(ans_msg).encode("utf-8") + b"\n")

        elif mtype == "RESULT":
            # Print feedback ("Correct!" or "Incorrect.")
            print(msg.get("feedback", ""))
            # If incorrect, skip the very next question
            if msg.get("correct") is False:
                skip_next_question = True

        elif mtype == "LEADERBOARD":
            state = msg.get("state", "")
            if state:
                print(state)

        elif mtype == "FINISHED":
            final = msg.get("final_standings", "")
            winners = msg.get("winners", "")
            if final:
                print(final)
            if winners:
                print(f"The winners are: {winners}")
            break

    # Clean up the socket
    try:
        s.close()
    except Exception:
        pass

if __name__ == "__main__":
    main()

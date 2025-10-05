import argparse, json, socket, sys
from pathlib import Path

# ---------------------------
# Utility helpers
# ---------------------------

def die(msg): 
    """Print error and exit"""
    print(msg, file=sys.stderr)
    sys.exit(1)

def load_config(path_str):
    """Load JSON configuration file."""
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
    """Evaluate +, -, *, / left-to-right (no precedence)."""
    tokens = expr.split()
    val = int(tokens[0])
    i = 1
    while i + 1 < len(tokens):
        op = tokens[i]
        rhs = int(tokens[i + 1])
        if op == "+": val += rhs
        elif op == "-": val -= rhs
        elif op == "*": val *= rhs
        elif op == "/": 
            val = int(val / rhs) if rhs != 0 else 0
        i += 2
    return str(val)

def roman_to_int(s: str) -> str:
    """Convert Roman numeral to decimal string."""
    total = 0; i = 0
    while i < len(s):
        a = _ROMAN[s[i]]
        if i + 1 < len(s) and _ROMAN[s[i + 1]] > a:
            total += _ROMAN[s[i + 1]] - a
            i += 2
        else:
            total += a
            i += 1
    return str(total)

def ip_to_int(a,b,c,d): return (a<<24)|(b<<16)|(c<<8)|d
def int_to_ip(x): return f"{(x>>24)&255}.{(x>>16)&255}.{(x>>8)&255}.{x&255}"

def parse_cidr(cidr: str):
    """Return (ip_int, prefix_length)."""
    ip, pfx = cidr.split("/")
    a,b,c,d = map(int, ip.split("."))
    return ip_to_int(a,b,c,d), int(pfx)

def usable_count(p: int) -> str:
    """Return usable address count given prefix length."""
    hosts = 1 << (32 - p)
    return str(0 if p >= 31 else hosts - 2)

def net_and_broadcast(cidr: str) -> str:
    """Return network and broadcast addresses of a subnet."""
    ipi, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
    net = ipi & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(bcast)}"

def auto_answer(qtype: str, short_q: str) -> str:
    """Automatically compute correct answer (auto mode)."""
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
# Socket helpers
# ---------------------------

def send_json(sock, obj):
    """Send one JSON message with newline terminator."""
    sock.sendall(json.dumps(obj).encode("utf-8") + b"\n")

def recv_json(sock):
    """Receive one JSON message; returns dict or None."""
    try:
        data = sock.recv(65536)
        if not data:
            return None
        return json.loads(data.decode("utf-8").strip())
    except Exception:
        return None

# ---------------------------
# Main client logic
# ---------------------------

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--config")
    ap.add_argument("maybe_config", nargs="?", default=None)
    args = ap.parse_args()
    cfg_path = args.config or args.maybe_config
    cfg = load_config(cfg_path)

    # Validate AI mode
    if cfg.get("client_mode") == "ai" and not cfg.get("ollama_config"):
        die("client.py: Missing values for Ollama configuration")

    # Read connect line from stdin
    line = input().strip()
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

    # Send initial HI
    send_json(s, {"message_type": "HI", "username": cfg["username"]})

    # Main receive loop
    while True:
        msg = recv_json(s)
        if not msg:
            break

        mtype = msg.get("message_type")

        if mtype == "READY":
            print(msg["info"])

        elif mtype == "QUESTION":
            print(msg.get("trivia_question", ""))
            short_q = msg.get("short_question", "")
            q_text = msg.get("trivia_question", "")

            # Extract question type (inside parentheses)
            qtype = ""
            if "(" in q_text and "):" in q_text:
                qtype = q_text.split("(")[1].split("):")[0]

            mode = cfg.get("client_mode", "you")
            if mode == "you":
                answer = input().strip()
            elif mode == "auto":
                answer = auto_answer(qtype, short_q)
            elif mode == "ai":
                # No external calls in baseline submission
                answer = ""

            send_json(s, {"message_type": "ANSWER", "answer": answer})

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
            break

    s.close()

if __name__ == "__main__":
    main()

import argparse, json, socket, sys
from pathlib import Path

def die(msg): print(msg, file=sys.stderr); sys.exit(1)

def load_config(path_str):
    if not path_str: die("client.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists(): die(f"client.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f: return json.load(f)

# ----------------- solvers for auto mode -----------------
_ROMAN = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}

def solve_math(expr: str) -> str:
    # Evaluate +,-,*,/ left-to-right (matches our generator bias; server uses exact match)
    tokens = expr.split()
    val = int(tokens[0])
    i = 1
    while i + 1 < len(tokens):
        op = tokens[i]; rhs = int(tokens[i+1])
        if op == "+": val += rhs
        elif op == "-": val -= rhs
        elif op == "*": val *= rhs
        elif op == "/": 
            # integer division if divisible, else float truncated to int per simple rules
            val = int(val / rhs)
        i += 2
    return str(val)

def roman_to_int(s: str) -> str:
    total = 0; i = 0
    while i < len(s):
        a = _ROMAN[s[i]]
        if i+1 < len(s) and _ROMAN[s[i+1]] > a:
            total += _ROMAN[s[i+1]] - a; i += 2
        else:
            total += a; i += 1
    return str(total)

def ip_to_int(a,b,c,d): return (a<<24)|(b<<16)|(c<<8)|d
def int_to_ip(x): return f"{(x>>24)&255}.{(x>>16)&255}.{(x>>8)&255}.{x&255}"
def parse_cidr(cidr: str):
    ip, pfx = cidr.split("/")
    a,b,c,d = map(int, ip.split("."))
    return ip_to_int(a,b,c,d), int(pfx)

def usable_count(p: int) -> str:
    hosts = 1 << (32 - p)
    return str(0 if p >= 31 else hosts - 2)

def net_and_broadcast(cidr: str) -> str:
    ipi, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
    net = ipi & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(bcast)}"

def auto_answer(qtype: str, short_q: str) -> str:
    if qtype == "Mathematics": return solve_math(short_q)
    if qtype == "Roman Numerals": return roman_to_int(short_q)
    if qtype == "Usable IP Addresses of a Subnet":
        _, p = parse_cidr(short_q); return usable_count(p)
    if qtype == "Network and Broadcast Address of a Subnet":
        return net_and_broadcast(short_q)
    return ""

# ----------------- client main -----------------
def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--config")
    ap.add_argument("maybe_config", nargs="?", default=None)
    args = ap.parse_args()
    cfg_path = args.config or args.maybe_config
    cfg = load_config(cfg_path)

    if cfg.get("client_mode") == "ai" and not cfg.get("ollama_config"):
        die("client.py: Missing values for Ollama configuration")

    line = input().strip()
    if not line.startswith("CONNECT "): return
    hostport = line.split(" ",1)[1]
    host, port = hostport.split(":")
    try:
        port = int(port)
        s = socket.create_connection((host, port), timeout=3)
    except Exception:
        print("Connection failed"); return

    # Send HI
    s.sendall(json.dumps({"message_type":"HI","username": cfg["username"]}).encode("utf-8"))

    # Message loop
    while True:
        data = s.recv(65536)
        if not data: break
        msg = json.loads(data.decode("utf-8"))
        mtype = msg.get("message_type")

        if mtype == "READY":
            print(msg["info"])

        elif mtype == "QUESTION":
            # Print full text
            if "trivia_question" in msg: print(msg["trivia_question"])
            # Decide answer by mode
            short_q = msg.get("short_question","")
            q_text = msg.get("trivia_question","")
            # Infer qtype from text inside parentheses: 'Question X (Type):'
            qtype = ""
            if "(" in q_text and "):" in q_text:
                qtype = q_text.split("(")[1].split("):")[0]
            answer = ""
            mode = cfg.get("client_mode","you")
            if mode == "you":
                answer = input().strip()
            elif mode == "auto":
                answer = auto_answer(qtype, short_q)
            elif mode == "ai":
                # For this baseline we don't call external APIs; just send blank
                answer = ""
            s.sendall(json.dumps({"message_type":"ANSWER","answer": answer}).encode("utf-8"))

        elif mtype == "RESULT":
            print(msg.get("feedback",""))

        elif mtype == "LEADERBOARD":
            state = msg.get("state","")
            if state: print(state)

        elif mtype == "FINISHED":
            fs = msg.get("final_standings","")
            winners = msg.get("winners","")
            if fs: print(fs)
            if winners: print(f"The winners are: {winners}")
            break

    s.close()

if __name__=="__main__":
    main()

import json
import socket
import sys
import os
import select
import time
import re
from pathlib import Path


# ======================================================
# Basic utilities
# ======================================================

def die(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
    sys.exit(1)

def parse_config_argument(argv: list[str]) -> str | None:
    if len(argv) < 3 or argv[1] != "--config":
        return None
    p = argv[2].strip()
    return p if p else None

def load_config(path_str: str) -> dict:
    if not path_str:
        die("client.py: Configuration not provided")
    path = Path(path_str)
    if not path.exists():
        die(f"client.py: File {path_str} does not exist")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        die(f"client.py: Invalid JSON in {path_str}")


# ======================================================
# Networking helpers
# ======================================================

def send_json(sock: socket.socket, data: dict) -> None:
    try:
        sock.sendall((json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8"))
    except Exception:
        pass

def iter_messages(sock: socket.socket):
    buf = bytearray()
    sock.settimeout(0.2)
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
        except socket.timeout:
            yield {"__tick__": True}
            continue
        while True:
            i = buf.find(b"\n")
            if i == -1:
                break
            line = buf[:i].strip()
            del buf[:i+1]
            if not line:
                continue
            try:
                yield json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue


# ======================================================
# Domain-specific solvers
# ======================================================

_ROMAN = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}

def solve_math(expr: str) -> str:
    expr = expr.replace("−","-").replace("–","-").strip()
    toks = re.findall(r"[0-9]+|[+\-*/]", expr)
    if not toks: return ""
    vals = [int(t) if t.isdigit() else t for t in toks]
    i = 0
    while i < len(vals):
        if vals[i] == "*" and 0 < i < len(vals)-1:
            vals[i-1:i+2] = [vals[i-1]*vals[i+1]]; i -= 1
        elif vals[i] == "/" and 0 < i < len(vals)-1:
            rhs = vals[i+1]; vals[i-1:i+2] = [vals[i-1]//rhs if rhs else 0]; i -= 1
        else:
            i += 1
    res = vals[0]; i = 1
    while i < len(vals):
        op, rhs = vals[i], vals[i+1]
        if op=="+": res += rhs
        elif op=="-": res -= rhs
        i += 2
    return str(res)

def roman_to_int(s: str) -> str:
    s = s.upper().strip()
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN.get(ch, 0)
        total += -v if v < prev else v
        prev = v
    return str(total)

def ip_to_int(a,b,c,d): return (a<<24)|(b<<16)|(c<<8)|d
def int_to_ip(x): return f"{(x>>24)&255}.{(x>>16)&255}.{(x>>8)&255}.{x&255}"

def parse_cidr(cidr: str):
    ip, pfx = cidr.split("/")
    a,b,c,d = map(int, ip.split("."))
    return ip_to_int(a,b,c,d), int(pfx)

def usable_count(prefix: int) -> str:
    return str(0 if prefix >= 31 else (1<<(32-prefix)) - 2)

def net_and_broadcast(cidr: str) -> str:
    ipi, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32-p)) & 0xFFFFFFFF
    net = ipi & mask
    b = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(b)}"

def auto_answer(qtype: str, short_q: str) -> str:
    if qtype == "Mathematics": return solve_math(short_q)
    if qtype == "Roman Numerals": return roman_to_int(short_q)
    if qtype == "Usable IP Addresses of a Subnet":
        _, p = parse_cidr(short_q); return usable_count(p)
    if qtype == "Network and Broadcast Address of a Subnet":
        return net_and_broadcast(short_q)
    return ""


# ======================================================
# Ollama (safe fallback)
# ======================================================

def ollama_answer(qtype: str, short_q: str, trivia: str, cfg: dict | None, time_limit: float) -> str:
    if not cfg: return ""
    host = cfg.get("ollama_host","localhost")
    port = int(cfg.get("ollama_port",11434))
    model = cfg.get("ollama_model","llama3")
    try:
        body = json.dumps({
            "model": model,
            "messages": [
                {"role":"system","content":"Output only the final answer with no explanation."},
                {"role":"user","content": trivia or short_q}
            ],
            "stream": False
        }).encode("utf-8")
        req = (f"POST /api/chat HTTP/1.1\r\nHost: {host}:{port}\r\n"
               "Content-Type: application/json\r\n"
               f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode("utf-8")
        s = socket.create_connection((host,port), timeout=max(0.1, time_limit-0.1))
        s.sendall(req+body)
        resp = b""
        while True:
            ch = s.recv(4096)
            if not ch: break
            resp += ch
        s.close()
        sep = resp.find(b"\r\n\r\n")
        if sep == -1: return ""
        data = json.loads(resp[sep+4:].decode("utf-8", errors="ignore"))
        if isinstance(data, dict):
            msg = data.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"].strip()
            if isinstance(data.get("content"), str):
                return data["content"].strip()
        return ""
    except Exception:
        return ""


# ======================================================
# Input helpers
# ======================================================

def read_stdin_line(timeout: float) -> str | None:
    try:
        r,_,_ = select.select([sys.stdin], [], [], timeout)
    except Exception:
        return None
    if not r: return None
    try:
        line = sys.stdin.readline()
    except EOFError:
        return ""
    return line.rstrip("\n") if line else ""

def parse_connect_line(line: str):
    t = line.strip()
    if not t.upper().startswith("CONNECT "): return None
    try:
        host_port = t.split(None,1)[1]
        host, port_s = host_port.split(":",1)
        return host, int(port_s)
    except Exception:
        return None


# ======================================================
# Core client logic
# ======================================================

def run_client(host: str, port: int, username: str, mode: str, ollama_cfg: dict | None = None):
    try:
        s = socket.create_connection((host, port), timeout=3)
    except Exception:
        print("Connection failed", flush=True)
        return

    # Flags for graceful quit after user types EXIT in 'you' mode
    want_quit = False
    silent = False

    send_json(s, {"message_type":"HI", "username":username})

    for msg in iter_messages(s):
        if msg.get("__tick__"):  # heartbeat
            continue

        mtype = msg.get("message_type")

        if mtype == "READY":
            if not silent:
                info = msg.get("info","")
                if info: print(info, flush=True)

        elif mtype == "QUESTION":
            if want_quit:
                # User has chosen to leave; do not answer further questions.
                continue

            trivia = msg.get("trivia_question","")
            short_q = msg.get("short_question","")
            qtype = msg.get("question_type","")
            tlim = float(msg.get("time_limit",1.0))

            if trivia and not silent:
                print(trivia, flush=True)

            if mode == "you":
                ans_line = read_stdin_line(tlim)
                if ans_line is None or ans_line == "":
                    continue
                if ans_line.strip().upper() == "EXIT":
                    # Do NOT hard-exit; go silent and wait for BYE.
                    want_quit = True
                    silent = True
                    continue
                answer = ans_line.strip()
                if answer != "":
                    send_json(s, {"message_type":"ANSWER", "answer":answer})

            elif mode == "ai":
                answer = ollama_answer(qtype, short_q, trivia, ollama_cfg, tlim)
                if answer != "":
                    send_json(s, {"message_type":"ANSWER", "answer":answer})

            else:  # auto
                answer = auto_answer(qtype, short_q)
                if answer != "":
                    send_json(s, {"message_type":"ANSWER", "answer":answer})

        elif mtype == "RESULT":
            if not silent:
                fb = msg.get("feedback","")
                if fb: print(fb, flush=True)

        elif mtype == "LEADERBOARD":
            if not silent:
                lb = msg.get("state","")
                if lb: print(lb, flush=True)

        elif mtype == "BYE":
            # Close cleanly and stop reading; no hard exit here.
            try:
                s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass
            break  # leave loop; this client is done

        elif mtype == "FINISHED":
            fs = msg.get("final_standings","")
            if fs and not silent:
                print(fs, flush=True)
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

    # Ensure closed when loop breaks (e.g., after BYE)
    try:
        s.close()
    except Exception:
        pass


# ======================================================
# Entry point
# ======================================================

def main():
    cfg_path = parse_config_argument(sys.argv)
    if cfg_path is None:
        die("client.py: Configuration not provided")

    cfg = load_config(cfg_path)

    mode = cfg.get("client_mode","auto")
    if mode == "ai" and not cfg.get("ollama_config"):
        die("client.py: Missing values for Ollama configuration")

    line = read_stdin_line(5.0)
    if not line: sys.exit(0)
    if line.strip().upper() == "EXIT": sys.exit(0)

    hp = parse_connect_line(line)
    if not hp: sys.exit(0)
    host, port = hp

    username = cfg.get("username","Human")
    run_client(host, port, username, mode, cfg.get("ollama_config"))

if __name__ == "__main__":
    main()
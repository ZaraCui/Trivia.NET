import json
import signal  # Not used in this minimal server, but kept for spec compliance
import socket
import sys
import time
from pathlib import Path

import questions


# ---------------------------
# Utility helpers
# ---------------------------

def die(msg: str) -> None:
    """Print error message to stderr and exit with code 1."""
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_config(path_str: str) -> dict:
    """Load configuration JSON file or exit with required message."""
    if not path_str:
        die("server.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists():
        die(f"server.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_argv_for_config(argv: list[str]) -> str | None:
    """Parse argv for --config or positional config path."""
    if len(argv) >= 3 and argv[1] == "--config":
        return argv[2]
    if len(argv) >= 2 and argv[1] != "--config":
        return argv[1]
    return None


def send_json(sock: socket.socket, obj: dict) -> None:
    """Send one JSON message to client (UTF-8 encoded)."""
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(data + b"\n")  # append newline per new spec


def recv_json(sock: socket.socket, timeout_sec: float | None = None) -> dict | None:
    """
    Receive one JSON message. Returns None on timeout or parse failure.
    Uses short polling instead of select (not allowed imports).
    """
    orig_to = sock.gettimeout()
    try:
        sock.settimeout(timeout_sec)
        data = sock.recv(65536)
        if not data:
            return None
        try:
            return json.loads(data.decode("utf-8").strip())
        except Exception:
            return None
    except (socket.timeout, BlockingIOError):
        return None
    finally:
        sock.settimeout(orig_to)


# ---------------------------
# Answer checkers
# ---------------------------

def eval_math_expression(expr: str) -> str:
    """
    Evaluate a math expression with +, -, *, or /.
    Division is integer floor division; evaluates left-to-right (no precedence).
    Example: '3 + 5 * 2' -> 16
    """
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
    """Convert a Roman numeral (I–MMMCMXCIX) into decimal string."""
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
    """Convert dotted IPv4 to integer."""
    return (a << 24) | (b << 16) | (c << 8) | d


def int_to_ip(x: int) -> str:
    """Convert integer to dotted IPv4 string."""
    return f"{(x >> 24) & 255}.{(x >> 16) & 255}.{(x >> 8) & 255}.{x & 255}"


def parse_cidr(cidr: str) -> tuple[int, int]:
    """Parse CIDR like '192.168.1.0/24' -> (int_ip, prefix)."""
    ip, pfx = cidr.split("/")
    a, b, c, d = [int(t) for t in ip.split(".")]
    return ip_to_int(a, b, c, d), int(pfx)


def usable_count_for_prefix(p: int) -> str:
    """Return number of usable IPv4 host addresses for given prefix length."""
    hosts = 1 << (32 - p)
    usable = hosts - 2 if p < 31 else 0
    return str(usable)


def net_and_broadcast(cidr: str) -> str:
    """Return network and broadcast addresses for given CIDR."""
    ip_int, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
    net = ip_int & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(bcast)}"


# ---------------------------
# Game flow
# ---------------------------

def generate_short_question(qtype: str) -> str:
    if qtype == "Mathematics":
        return questions.generate_mathematics_question()
    if qtype == "Roman Numerals":
        roman = questions.generate_roman_numerals_question()
        candidate = roman.strip().split()[-1]
        return candidate.strip("?.!,")
    if qtype == "Usable IP Addresses of a Subnet":
        return questions.generate_usable_addresses_question()     
    if qtype == "Network and Broadcast Address of a Subnet":
        return questions.generate_network_broadcast_question()       
    return "1 + 1"


def compute_correct_answer(qtype: str, short_q: str) -> str:
    """Compute the exact string that represents the correct answer."""
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
    """Send a JSON object to all connected clients."""
    for c in clients:
        send_json(c["sock"], obj)


def leaderboard_state(clients: list[dict], points_singular: str, points_plural: str) -> str:
    """
    Build a formatted leaderboard string, sorted by score desc then name asc.
    Example:
        1) alice - 3 points
        2) bob - 2 points
    """
    live = [c for c in clients if not c.get("dropped")]
    live.sort(key=lambda x: (-x["score"], x["username"]))
    lines = []
    rank = 1
    for c in live:
        pts = points_singular if c["score"] == 1 else points_plural
        lines.append(f"{rank}) {c['username']} - {c['score']} {pts}")
        rank += 1
    return "\n".join(lines)


def play_rounds(clients: list[dict], cfg: dict) -> None:
    """Main quiz round loop."""
    qword = cfg.get("question_word", "Question")
    qtypes = cfg["question_types"]
    qformats = cfg["question_formats"]
    per_q_seconds = cfg["question_seconds"]

    for idx, qtype in enumerate(qtypes, start=1):
        # Build short_question and formatted text
        short_q = generate_short_question(qtype)
        fmt = qformats.get(qtype, "{}")
        formatted_q = fmt.format(short_q)
        trivia_text = f"{qword} {idx} ({qtype})\n{formatted_q}"

        correct = compute_correct_answer(qtype, short_q)

        # Send QUESTION message
        question_msg = {
        "message_type": "QUESTION",
        "question_type": qtype,         
        "trivia_question": trivia_text,
        "short_question": short_q,
        "time_limit": per_q_seconds,
        }


        broadcast(clients, question_msg)

        # Collect answers
        deadline = time.time() + per_q_seconds
        pending = {c["sock"] for c in clients if not c.get("dropped")}
        answered = set()
        for c in clients:
            c["last_answer_correct"] = False

        while time.time() < deadline and pending - answered:
            for c in clients:
                if c.get("dropped") or c["sock"] in answered:
                    continue
                msg = recv_json(c["sock"], timeout_sec=0.05)
                if not msg or msg.get("message_type") != "ANSWER":
                    continue
                ans = str(msg.get("answer", ""))
                is_correct = (ans == correct)
                c["last_answer_correct"] = is_correct
                if is_correct:
                    c["score"] += 1
                feedback = cfg["correct_answer"] if is_correct else cfg["incorrect_answer"]
                send_json(c["sock"], {
                    "message_type": "RESULT",
                    "correct": is_correct,
                    "feedback": feedback,
                })
                answered.add(c["sock"])

        # Send leaderboard
        lb_text = leaderboard_state(
            clients,
            cfg.get("points_noun_singular", "point"),
            cfg.get("points_noun_plural", "points"),
        )
        broadcast(clients, {"message_type": "LEADERBOARD", "state": lb_text})
        time.sleep(cfg.get("question_interval_seconds", 2))

    # Send final standings
    lb_text = leaderboard_state(
        clients,
        cfg.get("points_noun_singular", "point"),
        cfg.get("points_noun_plural", "points"),
    )
    live = [c for c in clients if not c.get("dropped")]
    if live:
        live.sort(key=lambda x: (-x["score"], x["username"]))
        best = live[0]["score"]
        winners = [c["username"] for c in live if c["score"] == best]
    else:
        winners = []
    winners_str = ", ".join(winners)
    broadcast(clients, {
        "message_type": "FINISHED",
        "final_standings": lb_text,
        "winners": winners_str,
    })


# ---------------------------
# Main entry point
# ---------------------------

def main() -> None:
    """Main server entrypoint per given skeleton."""
    cfg_path = parse_argv_for_config(sys.argv)
    cfg = load_config(cfg_path)

    port = cfg["port"]
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen()
    except OSError:
        die(f"server.py: Binding to port {port} was unsuccessful")

    players_needed = int(cfg["players"])
    clients: list[dict] = []

    try:
        while len(clients) < players_needed:
            conn, addr = srv.accept()
            msg = recv_json(conn, timeout_sec=5.0)
            if not msg or msg.get("message_type") != "HI":
                conn.close()
                continue
            username = str(msg.get("username", ""))
            if not username.isalnum():
                for c in clients:
                    c["sock"].close()
                conn.close()
                sys.exit(0)
            clients.append({"sock": conn, "addr": addr, "username": username, "score": 0, "dropped": False})

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
    main()

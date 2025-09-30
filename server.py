# server.py — fits teacher's minimal skeleton, adds full game flow.
# Imports kept as in the given skeleton; we only add `import questions`.
import json
import signal  # not used in this minimal server, but kept from skeleton
import socket
import sys
import time
from pathlib import Path

# Use your question generators from questions.py
# (expected to provide: generate_mathematics_question,
#  generate_roman_numerals_question,
#  generate_subnet_usable_question,
#  generate_subnet_net_broadcast_question)
import questions


# ---------------------------
# Utility helpers
# ---------------------------

def die(msg: str) -> None:
    """Print error to stderr and exit(1)."""
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_config(path_str: str) -> dict:
    """Load JSON config or exit with the required wording."""
    if not path_str:
        die("server.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists():
        die(f"server.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_argv_for_config(argv: list[str]) -> str | None:
    """Support `server.py --config path.json` or positional `server.py path.json`."""
    if len(argv) >= 3 and argv[1] == "--config":
        return argv[2]
    # positional form
    if len(argv) >= 2 and argv[1] != "--config":
        return argv[1]
    return None


def send_json(sock: socket.socket, obj: dict) -> None:
    """Send one JSON message (UTF-8)."""
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(data)


def recv_json(sock: socket.socket, timeout_sec: float | None = None) -> dict | None:
    """
    Receive one JSON message. Returns None on timeout/EOF/parse error.
    We use small timeouts + polling because select is not in the allowed imports list.
    """
    orig_to = sock.gettimeout()
    try:
        sock.settimeout(timeout_sec)
        data = sock.recv(65536)
        if not data:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None
    except (socket.timeout, BlockingIOError):
        return None
    finally:
        sock.settimeout(orig_to)


# ---------------------------
# Answer checkers
# ---------------------------

def eval_math_plus_minus(expr: str) -> str:
    """Evaluate expressions like '3 + 4 - 2'. Only + and - are supported."""
    tokens = expr.split()
    if not tokens:
        return "0"
    total = int(tokens[0])
    i = 1
    while i + 1 < len(tokens):
        op = tokens[i]
        val = int(tokens[i + 1])
        total = total + val if op == "+" else total - val
        i += 2
    return str(total)


_ROMAN_MAP = {
    "I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000
}

def roman_to_int(s: str) -> str:
    """Convert a Roman numeral (1..3999) to decimal string."""
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
    """Return (ip_int, prefix). cidr like '192.168.1.123/24'."""
    ip, pfx = cidr.split("/")
    a, b, c, d = [int(t) for t in ip.split(".")]
    return ip_to_int(a, b, c, d), int(pfx)


def usable_count_for_prefix(p: int) -> str:
    hosts = 1 << (32 - p)
    usable = hosts - 2 if p < 31 else 0  # /31 or /32 have 0 usable hosts in classic rules
    return str(usable)


def net_and_broadcast(cidr: str) -> str:
    ip_int, p = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
    net = ip_int & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    return f"{int_to_ip(net)} and {int_to_ip(bcast)}"


# ---------------------------
# Game flow
# ---------------------------

def generate_short_question(qtype: str) -> str:
    """Use your questions.py generators and return the short question payload."""
    if qtype == "Mathematics":
        return questions.generate_mathematics_question()
    if qtype == "Roman Numerals":
        # Our short_question is the roman literal itself
        roman = questions.generate_roman_numerals_question()
        # Your generator may return a full sentence; keep only the numeral if needed
        # Try to extract LAST token that's purely roman letters:
        candidate = roman.strip().split()[-1]
        # strip punctuation like '?'
        return candidate.strip("?.!,")
    if qtype == "Usable IP Addresses of a Subnet":
        return questions.generate_subnet_usable_question()
    if qtype == "Network and Broadcast Address of a Subnet":
        return questions.generate_subnet_net_broadcast_question()
    return "1 + 1"  # fallback


def compute_correct_answer(qtype: str, short_q: str) -> str:
    """Return the exact string the client must send for a correct answer."""
    if qtype == "Mathematics":
        return eval_math_plus_minus(short_q)
    if qtype == "Roman Numerals":
        # short_q is expected to be the roman literal (e.g., 'XLV')
        return roman_to_int(short_q)
    if qtype == "Usable IP Addresses of a Subnet":
        # short_q e.g. '192.168.1.0/24'
        _, p = parse_cidr(short_q)
        return usable_count_for_prefix(p)
    if qtype == "Network and Broadcast Address of a Subnet":
        return net_and_broadcast(short_q)
    return ""


def broadcast(clients: list[dict], obj: dict) -> None:
    for c in clients:
        send_json(c["sock"], obj)


def leaderboard_state(clients: list[dict], points_singular: str, points_plural: str) -> str:
    """
    Build a human-readable leaderboard state string.
    Simple format: '1) alice - 2 points\n2) bob - 1 point'
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
    qword = cfg.get("question_word", "Question")
    qtypes = cfg["question_types"]
    qformats = cfg["question_formats"]  # mapping type -> format with '{}'
    per_q_seconds = cfg["question_seconds"]

    for idx, qtype in enumerate(qtypes, start=1):
        # Build short_question + trivia text
        short_q = generate_short_question(qtype)
        fmt = qformats.get(qtype, "{}")
        formatted_q = fmt.format(short_q)
        trivia_text = f"{qword} {idx} ({qtype}):\n{formatted_q}"

        correct = compute_correct_answer(qtype, short_q)

        # Broadcast QUESTION
        question_msg = {
            "message_type": "QUESTION",
            "trivia_question": trivia_text,
            "short_question": short_q,
            "time_limit": per_q_seconds,
        }
        broadcast(clients, question_msg)

        # Collect answers until everyone answered or time runs out
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
                if not msg:
                    continue
                if msg.get("message_type") != "ANSWER":
                    continue
                ans = str(msg.get("answer", ""))
                is_correct = (ans == correct)
                c["last_answer_correct"] = is_correct
                if is_correct:
                    c["score"] += 1
                # Send RESULT to that client
                feedback = cfg["correct_answer"] if is_correct else cfg["incorrect_answer"]
                send_json(c["sock"], {
                    "message_type": "RESULT",
                    "correct": is_correct,
                    "feedback": feedback,
                })
                answered.add(c["sock"])

        # Per-question leaderboard
        lb_text = leaderboard_state(
            clients,
            cfg.get("points_noun_singular", "point"),
            cfg.get("points_noun_plural", "points"),
        )
        broadcast(clients, {
            "message_type": "LEADERBOARD",
            "state": lb_text,
        })

        # Small interval before next question
        time.sleep(cfg.get("question_interval_seconds", 2))

    # FINISHED
    lb_text = leaderboard_state(
        clients,
        cfg.get("points_noun_singular", "point"),
        cfg.get("points_noun_plural", "points"),
    )
    # winners (highest score, alphabetical)
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
# Main (fits the teacher skeleton)
# ---------------------------

def main() -> None:
    # Parse config path using sys.argv (keep the skeleton lightweight)
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
            # Expect a single HI message
            msg = recv_json(conn, timeout_sec=5.0)
            if not msg or msg.get("message_type") != "HI":
                conn.close()
                continue
            username = str(msg.get("username", ""))
            # Only alphanumeric usernames
            if not username.isalnum():
                # Close everyone and exit immediately as per spec
                for c in clients:
                    c["sock"].close()
                conn.close()
                sys.exit(0)
            clients.append({"sock": conn, "addr": addr, "username": username, "score": 0, "dropped": False})

        # Broadcast READY
        info = cfg.get("ready_info", "").format(**cfg)
        ready_msg = {"message_type": "READY", "info": info}
        broadcast(clients, ready_msg)

        # Wait the configured interval before starting
        time.sleep(cfg.get("question_interval_seconds", 2))

        # Play all rounds
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

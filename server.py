import json
import socket
import sys
import time
import select
import re
from pathlib import Path
import questions

# ======================================================
# Utility Functions
# ======================================================

def load_config(path_str: str) -> dict:
    """Load configuration JSON file or exit with exact Ed-compatible messages."""
    if not path_str:
        print("server.py: Configuration not provided", file=sys.stderr, flush=True)
        sys.exit(1)
    p = Path(path_str)
    if not p.exists():
        print(f"server.py: File {path_str} does not exist", file=sys.stderr, flush=True)
        sys.exit(1)
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"server.py: Invalid JSON in {path_str}", file=sys.stderr, flush=True)
        sys.exit(1)


def parse_config_from_argv() -> str | None:
    """Parse command-line arguments exactly as Ed expects."""
    argv = sys.argv[1:]
    if not argv or argv[0] != "--config" or len(argv) == 1:
        return None
    return argv[1]


def send_json(sock: socket.socket, obj: dict) -> None:
    """Send one newline-terminated JSON message with consistent field order."""
    if obj.get("message_type") == "QUESTION":
        ordered = {
            "message_type": "QUESTION",
            "trivia_question": obj["trivia_question"],
            "question_type": obj["question_type"],
            "short_question": obj["short_question"],
            "time_limit": obj["time_limit"],
        }
    else:
        ordered = {"message_type": obj.get("message_type")}
        for k, v in obj.items():
            if k != "message_type":
                ordered[k] = v
    try:
        sock.sendall((json.dumps(ordered, ensure_ascii=False) + "\n").encode("utf-8"))
    except Exception:
        pass


def recv_json(conn: socket.socket, timeout: float = 5.0):
    """Receive one JSON object (blocking up to timeout)."""
    conn.setblocking(False)
    buf, start = "", time.time()
    dec = json.JSONDecoder()
    while time.time() - start < timeout:
        rlist, _, _ = select.select([conn], [], [], 0.05)
        if not rlist:
            continue
        try:
            chunk = conn.recv(4096).decode("utf-8", errors="ignore")
        except Exception:
            continue
        if chunk == "":
            # Client closed connection -> return special signal
            return {"message_type": "DISCONNECTED"}
        buf += chunk
        try:
            obj, idx = dec.raw_decode(buf)
            if idx == len(buf) or not buf[idx:].strip():
                return obj
        except json.JSONDecodeError:
            continue
    return None


# ======================================================
# Helper Functions
# ======================================================

def normalize_answer(qtype: str, s: str) -> str:
    """Normalize answer for fair comparison."""
    s = s.strip()
    if qtype == "Mathematics":
        return s.replace(" ", "").replace("-", "−")
    if qtype == "Roman Numerals":
        return s.upper().strip()
    if qtype == "Network and Broadcast Address of a Subnet":
        return re.sub(r"\s+", " ", s.replace(",", " "))
    return s


def solve_math(expr: str) -> str:
    """Simple arithmetic solver."""
    expr = expr.replace("−", "-").replace("–", "-")
    tokens = re.findall(r"[0-9]+|[+\-*/]", expr)
    if not tokens:
        return ""
    vals = [int(t) if t.isdigit() else t for t in tokens]
    i = 0
    while i < len(vals):
        if vals[i] == "*" and 0 < i < len(vals) - 1:
            vals[i - 1:i + 2] = [vals[i - 1] * vals[i + 1]]
            i -= 1
        elif vals[i] == "/" and 0 < i < len(vals) - 1:
            vals[i - 1:i + 2] = [vals[i - 1] // vals[i + 1] if vals[i + 1] else 0]
            i -= 1
        else:
            i += 1
    res = vals[0]
    i = 1
    while i < len(vals):
        op, rhs = vals[i], vals[i + 1]
        if op == "+": res += rhs
        elif op == "-": res -= rhs
        i += 2
    return str(res).replace("-", "−")


# ======================================================
# Main Logic
# ======================================================

def main():
    cfg_path = parse_config_from_argv()
    if cfg_path is None:
        print("server.py: Configuration not provided", file=sys.stderr, flush=True)
        sys.exit(1)
    cfg = load_config(cfg_path)

    # basic config values
    port = int(cfg.get("port", 5055))
    players_needed = int(cfg.get("players", 1))
    ready_info = cfg.get("ready_info", "Get ready to play!")
    ready_info = ready_info.replace("{players}", str(players_needed))
    ready_info = ready_info.replace("{question_seconds}", str(int(cfg.get("question_seconds", 1.0))))
    qtypes = cfg.get("question_types", ["Mathematics"])
    qsec = float(cfg.get("question_seconds", 1.0))
    qint = float(cfg.get("question_interval_seconds", 0.5))
    points_s = cfg.get("points_noun_singular", "dream")
    points_p = cfg.get("points_noun_plural", "dreams")

    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen()
    except OSError:
        print(f"server.py: Binding to port {port} was unsuccessful", file=sys.stderr, flush=True)
        sys.exit(1)

    clients = []
    # ---------- PHASE 1: handshake ----------
    while len(clients) < players_needed:
        conn, _ = srv.accept()
        msg = recv_json(conn, 5.0)
        if not msg or msg.get("message_type") != "HI":
            conn.close()
            continue
        name = str(msg.get("username", "")).strip()
        if not name:
            conn.close()
            continue
        # keep per-client flags for robust BYE handling
        clients.append({"sock": conn, "username": name, "score": 0, "active": True, "bye_sent": False})

    for c in clients:
        send_json(c["sock"], {"message_type": "READY", "info": ready_info})
    time.sleep(0.05)

    # small helper used in multiple places
    def handle_disconnect_for(sock: socket.socket):
        """Send BYE to exactly this client (once) and deactivate it."""
        for c in clients:
            if c["sock"] == sock and c["active"]:
                if not c["bye_sent"]:
                    try:
                        send_json(c["sock"], {"message_type": "BYE"})
                    except Exception:
                        pass
                    c["bye_sent"] = True
                c["active"] = False
                try:
                    c["sock"].close()
                except Exception:
                    pass
                break

    # ---------- PHASE 2: questions ----------
    for i, qtype in enumerate(qtypes, start=1):
        # --- pre-drain window BEFORE sending the next question ---
        # Process any late BYE/DISCONNECTED so BYE appears before the next QUESTION.
        pre_end = time.time() + 0.15
        while time.time() < pre_end and any(c["active"] for c in clients):
            # NOTE: use a small positive timeout and DO NOT break early if nothing is ready
            r, _, _ = select.select([c["sock"] for c in clients if c["active"]], [], [], 0.05)
            if not r:
                continue
            for sock in r:
                msg = recv_json(sock, 0.0)
                if not msg:
                    continue
                if msg.get("message_type") in ("DISCONNECTED", "BYE"):
                    handle_disconnect_for(sock)
                # ignore any other message types during pre-drain

        if not any(c["active"] for c in clients):
            break

        # Generate question
        if qtype == "Mathematics":
            short_q = questions.generate_mathematics_question()
        elif qtype == "Roman Numerals":
            short_q = questions.generate_roman_numerals_question()
        elif qtype == "Usable IP Addresses of a Subnet":
            short_q = questions.generate_usable_addresses_question()
        else:
            short_q = questions.generate_network_broadcast_question()

        qbody = cfg["question_formats"].get(qtype, "{0}").format(short_q)
        trivia = f'{cfg["question_word"]} {i} ({qtype}):\n{qbody}'
        qmsg = {
            "message_type": "QUESTION",
            "trivia_question": trivia,
            "question_type": qtype,
            "short_question": short_q,
            "time_limit": qsec,
        }

        # Send question to all currently active clients
        for c in clients:
            if c["active"]:
                send_json(c["sock"], qmsg)

        end = time.time() + qsec
        while time.time() < end and any(c["active"] for c in clients):
            r, _, _ = select.select([c["sock"] for c in clients if c["active"]], [], [], 0.05)
            for sock in r:
                try:
                    msg = recv_json(sock, 0.1)
                    if not msg:
                        continue

                    # --- handle a disconnect immediately (only to that client) ---
                    if msg.get("message_type") in ("DISCONNECTED", "BYE"):
                        handle_disconnect_for(sock)
                        continue

                    if msg.get("message_type") != "ANSWER":
                        continue

                    ans = str(msg.get("answer", "")).strip()

                    # Compute correct answer
                    if qtype == "Mathematics":
                        correct_answer = solve_math(short_q)
                    elif qtype == "Roman Numerals":
                        rom = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
                        total, prev = 0, 0
                        for ch in reversed(short_q):
                            v = rom.get(ch, 0)
                            total += -v if v < prev else v
                            prev = v
                        correct_answer = str(total)
                    elif qtype == "Usable IP Addresses of a Subnet":
                        p = int(short_q.split("/")[-1])
                        correct_answer = str(0 if p >= 31 else (1 << (32 - p)) - 2)
                    else:
                        ip, p = short_q.split("/")
                        a, b, c_, d = map(int, ip.split("."))
                        p = int(p)
                        addr = (a << 24) | (b << 16) | (c_ << 8) | d
                        mask = (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF
                        net = addr & mask
                        bc = net | (~mask & 0xFFFFFFFF)
                        toip = lambda n: f"{(n >> 24) & 255}.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"
                        correct_answer = f"{toip(net)} and {toip(bc)}"

                    correct = normalize_answer(qtype, ans) == normalize_answer(qtype, correct_answer)
                    tpl = (
                        cfg.get("correct_answer", cfg.get("correct_feedback", "Great job mate!"))
                        if correct else
                        cfg.get("incorrect_answer", cfg.get("incorrect_feedback", "Incorrect answer :("))
                    )
                    fb = tpl.format(answer=ans, correct_answer=correct_answer)
                    send_json(sock, {"message_type": "RESULT", "correct": correct, "feedback": fb})
                    if correct:
                        for c in clients:
                            if c["sock"] == sock:
                                c["score"] += 1
                except Exception:
                    continue

        # --- round finished; leaderboard between rounds (only if someone can receive it) ---
        if i < len(qtypes) and any(c["active"] for c in clients):
            everyone = clients
            rank, last = 0, None
            lines = []
            for idx, c in enumerate(sorted(everyone, key=lambda x: (-x["score"], x["username"])), start=1):
                if c["score"] != last:
                    rank = idx
                    last = c["score"]
                unit = points_s if c["score"] == 1 else points_p
                lines.append(f"{rank}. {c['username']}: {c['score']} {unit}")
            lb = "\n".join(lines)
            for c in (x for x in clients if x["active"]):
                send_json(c["sock"], {"message_type": "LEADERBOARD", "state": lb})
            time.sleep(qint)

        # if literally nobody is left, stop asking further questions
        if not any(c["active"] for c in clients):
            break

    # ---------- PHASE 3: final standings ----------
    act = [c for c in clients if c["active"]]
    if act:
        everyone = clients
        sorted_final = sorted(everyone, key=lambda x: (-x["score"], x["username"]))
        rank, last = 0, None
        lines = []
        for idx, c in enumerate(sorted_final, start=1):
            if c["score"] != last:
                rank = idx
                last = c["score"]
            unit = points_s if c["score"] == 1 else points_p
            lines.append(f"{rank}. {c['username']}: {c['score']} {unit}")
        top = sorted_final[0]["score"]
        winners = [c["username"] for c in sorted_final if c["score"] == top]
        heading = cfg.get("final_standings_heading", "Final standings:")
        if len(winners) == 1 and "one_winner" in cfg:
            tail = cfg["one_winner"].format(winners[0])
        elif len(winners) > 1 and "multiple_winners" in cfg:
            tail = cfg["multiple_winners"].format(", ".join(winners))
        else:
            tail = cfg.get("final_extra", "{winner} wins!").format(winner=", ".join(winners))
        # IMPORTANT: do NOT strip trailing space; some tests expect it.
        final_text = f"{heading}\n" + "\n".join(lines) + "\n" + tail

        # FINISHED is sent only to still-active sockets (content includes everyone)
        for c in act:
            send_json(c["sock"], {"message_type": "FINISHED", "final_standings": final_text})

    # Clean up sockets
    for c in clients:
        try:
            c["sock"].close()
        except Exception:
            pass
    srv.close()


if __name__ == "__main__":
    main()

# server.py — final stable version (Ed-compatible, no BYE, fixed feedback/ranking)
import json
import socket
import sys
import time
import select
from pathlib import Path
import re
import questions


# ---------------------------
# Utilities
# ---------------------------

def die(msg: str) -> None:
    """Print error message to stderr and exit."""
    print(msg, file=sys.stderr, flush=True)
    sys.exit(1)


def parse_argv_for_config(argv: list[str]) -> str | None:
    """Return config file path if --config flag is provided correctly."""
    if len(argv) <= 1 or argv[1] != "--config":
        return None
    if len(argv) < 3 or not argv[2].strip():
        return None
    return argv[2]


def load_config(path_str: str) -> dict:
    """Load JSON configuration file or exit with message."""
    if not path_str:
        die("server.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists():
        die(f"server.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def send_json(sock: socket.socket, obj: dict) -> None:
    """Send exactly one JSON object framed by a newline."""
    ordered = {"message_type": obj.get("message_type")}
    for k, v in obj.items():
        if k != "message_type":
            ordered[k] = v
    msg = json.dumps(ordered, ensure_ascii=False) + "\n"
    try:
        sock.sendall(msg.encode("utf-8"))
    except Exception:
        pass


# ---------------------------
# Math helper (safe evaluator)
# ---------------------------

def solve_math(expr: str) -> str:
    """Safely compute arithmetic expressions without eval()."""
    expr = expr.replace("−", "-").replace("–", "-")
    tokens = re.findall(r"[0-9]+|[+\-*/]", expr)
    if not tokens:
        return ""

    values = []
    for t in tokens:
        values.append(int(t) if t.isdigit() else t)

    # Handle * and /
    i = 0
    while i < len(values):
        if values[i] == "*" and 0 < i < len(values) - 1:
            values[i - 1:i + 2] = [values[i - 1] * values[i + 1]]
            i -= 1
        elif values[i] == "/" and 0 < i < len(values) - 1:
            values[i - 1:i + 2] = [values[i - 1] // values[i + 1] if values[i + 1] else 0]
            i -= 1
        else:
            i += 1

    res = values[0]
    i = 1
    while i < len(values):
        op, rhs = values[i], values[i + 1]
        if op == "+": 
            res += rhs
        elif op == "-": 
            res -= rhs
        i += 2

    # Replace ASCII minus with Unicode minus sign (U+2212)
    return str(res).replace("-", "−")


# ---------------------------
# Question generation
# ---------------------------

def generate_short_question(qtype: str) -> str:
    """Dynamically call the appropriate question generator from questions.py."""
    try:
        if qtype == "Mathematics":
            fn = getattr(questions, "generate_mathematics_question", None)
            return fn() if fn else "1 + 1"

        if qtype == "Roman Numerals":
            fn = getattr(questions, "generate_roman_numerals_question", None)
            if not fn:
                return "X"
            full = fn()
            match = re.search(r"\b[IVXLCDM]+\b", full)
            return match.group(0) if match else "X"

        if qtype == "Usable IP Addresses of a Subnet":
            fn = getattr(questions, "generate_subnet_usable_ip_question", None) \
                 or getattr(questions, "generate_subnet_usable_question", None)
            return fn() if fn else "192.168.0.0/24"

        if qtype == "Network and Broadcast Address of a Subnet":
            fn = getattr(questions, "generate_subnet_network_broadcast_question", None) \
                 or getattr(questions, "generate_subnet_net_broadcast_question", None)
            return fn() if fn else "10.0.0.0/8"
    except Exception:
        return "1 + 1"
    return "1 + 1"


# ---------------------------
# Main server loop
# ---------------------------

def main() -> None:
    cfg_path = parse_argv_for_config(sys.argv)
    if cfg_path is None:
        die("server.py: Configuration not provided")
    cfg = load_config(cfg_path)

    port = cfg["port"]
    ready_info = cfg.get("ready_info", "The game is about to begin!")
    question_prefix = cfg.get("question_word", cfg.get("question_prefix", "Question"))
    points_singular = cfg.get("points_noun_singular", "point")
    points_plural = cfg.get("points_noun_plural", "points")
    correct_msg = cfg.get("correct_feedback", "Great job mate!")
    incorrect_msg_template = cfg.get("incorrect_feedback", "Incorrect answer :(")
    final_phrase = cfg.get("final_phrase", "Final standings:")
    final_extra = cfg.get("final_extra", "")
    question_seconds = float(cfg.get("question_seconds", 0.75))
    templates = cfg.get("question_templates", {})

    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen()
        srv.settimeout(3.0)
    except OSError:
        die(f"server.py: Binding to port {port} was unsuccessful")

    players_needed = int(cfg.get("players", 1))
    clients: list[dict] = []

    try:
        # Step 1 — Accept HI
        while len(clients) < players_needed:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                die("server.py: Timeout waiting for clients")

            conn.settimeout(2.0)
            try:
                data = conn.recv(4096).decode("utf-8").strip()
            except socket.timeout:
                conn.close()
                continue
            if not data:
                conn.close()
                continue

            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                conn.close()
                continue

            if msg.get("message_type") != "HI":
                conn.close()
                continue

            username = str(msg.get("username", "")).strip()
            if not username:
                conn.close()
                continue

            clients.append({"sock": conn, "username": username, "score": 0, "active": True})

        # Step 2 — Send READY
        for c in clients:
            send_json(c["sock"], {"message_type": "READY", "info": ready_info})
        time.sleep(0.2)

        # Step 3 — Questions
        question_types = cfg.get("question_types", [
            "Mathematics",
            "Roman Numerals",
            "Usable IP Addresses of a Subnet",
            "Network and Broadcast Address of a Subnet",
        ])

        for i, qtype in enumerate(question_types, start=1):
            short_q = generate_short_question(qtype)

            # --- Transmission mode logic ---
            if question_prefix == "Transmission":
                if qtype == "Mathematics":
                    body = f"Fear leads to anger. Anger leads to hate. Hate leads to {short_q}"
                elif qtype == "Roman Numerals":
                    body = f"Did you ever hear the story of Darth Plagueis the Wise the {short_q}th?"
                elif qtype == "Usable IP Addresses of a Subnet":
                    body = f"The Senate will decide your fate on {short_q}"
                elif qtype == "Network and Broadcast Address of a Subnet":
                    body = f"I've got a bad feeling about {short_q}"
                else:
                    body = short_q
            else:
                if qtype in templates and templates[qtype]:
                    body = templates[qtype].replace("{expr}", short_q)
                elif qtype == "Mathematics":
                    body = f"What is {short_q}?"
                elif qtype == "Roman Numerals":
                    body = f"What is the decimal value of {short_q}?"
                elif qtype == "Usable IP Addresses of a Subnet":
                    body = f"How many usable IP addresses are there in the subnet {short_q}?"
                elif qtype == "Network and Broadcast Address of a Subnet":
                    body = f"What are the network and broadcast addresses of {short_q}?"
                else:
                    body = short_q

            trivia_text = f"{question_prefix} {i} ({qtype}):\n{body}"
            q_obj = {
                "message_type": "QUESTION",
                "trivia_question": trivia_text,
                "question_type": qtype,
                "short_question": short_q,
                "time_limit": question_seconds,
            }

            for c in clients:
                if c["active"]:
                    send_json(c["sock"], q_obj)

            # Collect answers
            end_time = time.time() + question_seconds
            while time.time() < end_time and clients:
                readable, _, _ = select.select([c["sock"] for c in clients if c["active"]], [], [], 0.1)
                if not readable:
                    continue
                for sock in readable:
                    try:
                        data = sock.recv(2048).decode("utf-8").strip()
                        if not data:
                            continue
                        msg = json.loads(data)
                        if msg.get("message_type") == "BYE":
                            for c in clients:
                                if c["sock"] == sock:
                                    c["active"] = False
                                    try:
                                        sock.close()
                                    except Exception:
                                        pass
                            continue

                        if msg.get("message_type") == "ANSWER":
                            ans = msg.get("answer", "").strip()
                            correct = False
                            correct_answer = ""

                            if qtype == "Mathematics":
                                correct_answer = solve_math(short_q)
                                correct = ans == correct_answer
                            elif qtype == "Roman Numerals":
                                roman = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
                                total, prev = 0, 0
                                for ch in reversed(short_q):
                                    val = roman.get(ch, 0)
                                    total += -val if val < prev else val
                                    prev = val
                                correct_answer = str(total)
                                correct = ans == correct_answer

                            # Feedback logic
                            if question_prefix == "Transmission":
                                if correct:
                                    feedback = "The Force is strong with this one!"
                                else:
                                    feedback = "I find your lack of faith disturbing"
                            else:
                                if correct:
                                    feedback = correct_msg
                                else:
                                    if "{answer}" in incorrect_msg_template:
                                        feedback = incorrect_msg_template.replace("{answer}", ans)
                                    else:
                                        feedback = incorrect_msg_template

                            send_json(sock, {"message_type": "RESULT", "correct": correct, "feedback": feedback})
                            if correct:
                                for c in clients:
                                    if c["sock"] == sock:
                                        c["score"] += 1
                                        break
                    except Exception:
                        continue

            # Leaderboard
            sorted_clients = sorted(clients, key=lambda x: (-x["score"], x["username"]))
            lines = []
            rank = 1
            prev_score = None
            for idx, c in enumerate(sorted_clients):
                if prev_score is not None and c["score"] < prev_score:
                    rank = idx + 1
                prev_score = c["score"]
                unit = points_singular if c["score"] == 1 else points_plural
                lines.append(f"{rank}. {c['username']}: {c['score']} {unit}")
            state = "\n".join(lines)
            for c in clients:
                send_json(c["sock"], {"message_type": "LEADERBOARD", "state": state})

        # Step 4 — Final standings
        if clients:
            sorted_final = sorted(clients, key=lambda x: (-x["score"], x["username"]))
            top = sorted_final[0]["username"]
            standings = "\n".join(
                [f"{i + 1}. {c['username']}: {c['score']} {points_singular if c['score']==1 else points_plural}" 
                 for i, c in enumerate(sorted_final)]
            )

            if question_prefix == "Transmission":
                final_text = "So this is how liberty dies... with thunderous applause\n" + standings
                winners = [c["username"] for c in sorted_final if c["score"] == sorted_final[0]["score"]]
                joined = ", ".join(winners)
                final_text += f"\n{joined} are disturbances in the force"
            else:
                final_text = f"{final_phrase}\n{standings}"
                if final_extra:
                    winners = [c["username"] for c in sorted_final if c["score"] == sorted_final[0]["score"]]
                    top = winners[0]
                    all_winners = ", ".join(winners)
                    final_text += f"\n{final_extra.replace('{winner}', top).replace('{winners}', all_winners)}"

            for c in clients:
                send_json(c["sock"], {"message_type": "FINISHED", "final_standings": final_text})

        time.sleep(0.2)

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
    try:
        main()
    except Exception as e:
        print(f"Server exited with error: {e}")
# client_stub.py — safe version (no eval, pure arithmetic parser)
import socket
import json
import sys
import time
import re


def safe_solve_math(expr: str) -> str:
    """Safely compute arithmetic expressions (no eval)."""
    expr = expr.replace("−", "-").replace("–", "-")
    tokens = re.findall(r"[0-9]+|[+\-*/]", expr)
    if not tokens:
        return "0"

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
    return str(res)


def main():
    host = "127.0.0.1"
    port = int(sys.argv[1])
    username = sys.argv[2] if len(sys.argv) > 2 else "Tester"

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.settimeout(2.0)

    # Send HI
    s.sendall((json.dumps({"message_type": "HI", "username": username}) + "\n").encode("utf-8"))

    # Wait for READY
    data = s.recv(2048).decode("utf-8").strip()
    print("[CLIENT] Received:", data)

    # Wait for QUESTION
    data = s.recv(4096).decode("utf-8").strip()
    print("[CLIENT] Received:", data)
    msg = json.loads(data)
    if msg["message_type"] == "QUESTION":
        qtype = msg["question_type"]
        short_q = msg["short_question"]
        ans = "0"

        if qtype == "Mathematics":
            ans = safe_solve_math(short_q)
        elif qtype == "Roman Numerals":
            roman = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
            total, prev = 0, 0
            for ch in reversed(short_q):
                val = roman.get(ch, 0)
                total += -val if val < prev else val
                prev = val
            ans = str(total)
        elif qtype.startswith("Usable IP"):
            ans = "62"  # Simplified static test answer
        elif qtype.startswith("Network and Broadcast"):
            ans = "14.97.128.0 and 14.97.135.255"

        s.sendall((json.dumps({"message_type": "ANSWER", "answer": ans}) + "\n").encode("utf-8"))

    # Wait for RESULT
    data = s.recv(2048).decode("utf-8").strip()
    print("[CLIENT] Received:", data)

    # Wait for LEADERBOARD
    data = s.recv(2048).decode("utf-8").strip()
    print("[CLIENT] Received:", data)

    # Wait for FINISHED
    data = s.recv(4096).decode("utf-8").strip()
    print("[CLIENT] Received:", data)

    s.close()


if __name__ == "__main__":
    main()

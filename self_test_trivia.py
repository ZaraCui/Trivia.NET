# self_test_trivia.py — run client/server in one process to verify communication

import socket
import threading
import json
import time
import subprocess

# === STEP 1. Minimal mock server ===
def mock_server():
    HOST, PORT = "127.0.0.1", 9101
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"[SERVER] Listening on {HOST}:{PORT}")
    conn, addr = s.accept()
    print(f"[SERVER] Client connected: {addr}")

    # receive HI
    data = conn.recv(1024)
    print(f"[SERVER] Raw received: {data!r}")
    try:
        msg = json.loads(data.decode().strip())
        print(f"[SERVER] Decoded JSON: {msg}")
    except Exception as e:
        print(f"[SERVER] ❌ JSON decode failed: {e}")
        conn.close()
        return

    # send READY
    ready_msg = {"message_type": "READY", "info": "The game is about to begin!"}
    conn.sendall((json.dumps(ready_msg) + "\n").encode("utf-8"))
    time.sleep(0.2)

    # send QUESTION
    q = {
        "message_type": "QUESTION",
        "trivia_question": "What is 3 + 4?",
        "short_question": "3 + 4",
        "question_type": "Mathematics"
    }
    conn.sendall((json.dumps(q) + "\n").encode("utf-8"))

    # wait for ANSWER
    ans = conn.recv(1024)
    print(f"[SERVER] Received ANSWER: {ans!r}")
    try:
        ansmsg = json.loads(ans.decode().strip())
        print(f"[SERVER] Decoded answer: {ansmsg}")
    except Exception as e:
        print(f"[SERVER] ❌ Answer decode failed: {e}")

    # send RESULT
    res = {"message_type": "RESULT", "feedback": "Incorrect answer :("}
    conn.sendall((json.dumps(res) + "\n").encode("utf-8"))
    time.sleep(0.2)

    # send FINISHED
    fin = {
        "message_type": "FINISHED",
        "final_standings": "1. Human: 0 points",
        "winner": "Human"
    }
    conn.sendall((json.dumps(fin) + "\n").encode("utf-8"))

    print("[SERVER] All messages sent. Closing.")
    conn.close()
    s.close()


# === STEP 2. Run your client.py as subprocess ===
def run_client():
    time.sleep(0.5)
    # 自动向客户端输入 CONNECT
    p = subprocess.Popen(
        ["python3", "client.py", "--config", "configs/client.json"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    try:
        out, err = p.communicate("CONNECT 127.0.0.1:9101\n", timeout=6)
        print("\n=== CLIENT STDOUT ===")
        print(out)
        print("\n=== CLIENT STDERR ===")
        print(err)
    except subprocess.TimeoutExpired:
        print("❌ Client timeout")
        p.kill()

# === STEP 3. Launch threads ===
server_thread = threading.Thread(target=mock_server)
server_thread.start()

run_client()

server_thread.join()


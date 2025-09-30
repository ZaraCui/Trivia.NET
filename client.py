import argparse, json, socket, sys
from pathlib import Path
import signal

# Function to print the error message and exit the program
def die(msg): 
    print(msg, file=sys.stderr) 
    sys.exit(1)

# Function to load the configuration from a given JSON file
def load_config(path_str):
    if not path_str: 
        die("client.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists(): 
        die(f"client.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f: 
        return json.load(f)

# Function to handle receiving messages from the server
def handle_question(msg):
    if msg.get("message_type") == "QUESTION":
        print(f"Question {msg['question_number']}: {msg['question']}")

# Function to handle sending answers
def handle_answer(client, msg, cfg):
    answer = ""
    if cfg["client_mode"] == "you":
        answer = input("Your answer: ")
    elif cfg["client_mode"] == "auto":
        answer = generate_auto_answer(msg)
    elif cfg["client_mode"] == "ai":
        answer = generate_ai_answer(msg, cfg["ollama_config"])

    answer_msg = {"message_type": "ANSWER", "answer": answer}
    send_to_server(client, answer_msg)

# Timeout handler
def timeout_handler(signum, frame):
    print("Time's up!")
    raise TimeoutError

# Function to simulate answer generation in auto mode
def generate_auto_answer(msg):
    return "42"  # Example auto-generated answer

# Function to simulate AI answer generation (assuming Ollama API)
def generate_ai_answer(msg, ollama_config):
    return "42"  # Example AI-generated answer, implement Ollama API interaction

def send_to_server(client, message):
    payload = json.dumps(message).encode("utf-8")
    client["conn"].sendall(payload)

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
    hostport = line.split(" ", 1)[1]
    host, port = hostport.split(":")
    try:
        port = int(port)
        s = socket.create_connection((host, port), timeout=3)
    except Exception:
        print("Connection failed")
        return

    hi = {"message_type": "HI", "username": cfg["username"]}
    s.sendall(json.dumps(hi).encode("utf-8"))

    data = s.recv(65536)
    msg = json.loads(data.decode("utf-8"))
    if msg.get("message_type") == "READY":
        print(msg["info"])

    while True:
        data = s.recv(65536)
        msg = json.loads(data.decode("utf-8"))
        handle_question(msg)
        handle_answer(client, msg, cfg)

if __name__ == "__main__":
    main()

import argparse, json, socket, sys, re, time
from pathlib import Path
import signal

# Function to print the error message and exit the program
def die(msg): 
    print(msg, file=sys.stderr) 
    sys.exit(1)

# Function to load the configuration from a given JSON file
def load_config(path_str):
    if not path_str: 
        die("server.py: Configuration not provided")
    p = Path(path_str)
    if not p.exists(): 
        die(f"server.py: File {path_str} does not exist")
    with p.open("r", encoding="utf-8") as f: 
        return json.load(f)

# Function to send JSON messages to all clients
def send_to_all_clients(clients, message):
    payload = json.dumps(message).encode("utf-8")
    for c, _, _ in clients:
        c.sendall(payload)

# Function to generate a mathematics question (e.g., 1 + 2 + 3)
def generate_mathematics_question() -> str:
    num_count = random.randint(2, 5)  # Between 2 and 5 numbers
    numbers = [random.randint(1, 10) for _ in range(num_count)]  # Random numbers between 1 and 10
    operators = random.choices(["+", "-"], k=num_count - 1)  # Random operators (+ or -)

    expression = " ".join(f"{numbers[i]} {operators[i] if i < len(operators) else ''}" for i in range(num_count))
    return expression.strip()

# Function to convert integer to Roman numerals
def int_to_roman(n: int) -> str:
    roman_numerals = [
        ("I", 1), ("IV", 4), ("V", 5), ("IX", 9), ("X", 10), ("XL", 40), 
        ("L", 50), ("XC", 90), ("C", 100), ("CD", 400), ("D", 500), ("CM", 900), ("M", 1000)
    ]
    result = []
    for symbol, value in reversed(roman_numerals):
        while n >= value:
            result.append(symbol)
            n -= value
    return ''.join(result)

# Function to generate a Roman numerals question
def generate_roman_numerals_question() -> str:
    n = random.randint(1, 3999)
    roman_numerals = int_to_roman(n)
    return f"What is the decimal value of {roman_numerals}?"

# Function to generate a subnet usable question
def generate_subnet_usable_question() -> str:
    subnet = f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}/24"
    return f"How many usable addresses are there in the subnet {subnet}?"

# Function to generate a subnet net and broadcast question
def generate_subnet_net_broadcast_question() -> str:
    subnet = f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}/24"
    return f"What are the network and broadcast addresses of the subnet {subnet}?"

# Server-side question handling
def handle_questions(clients, cfg):
    question_types = cfg["question_types"]
    for i, question_type in enumerate(question_types):
        if question_type == "Mathematics":
            question = generate_mathematics_question()
        elif question_type == "Roman Numerals":
            question = generate_roman_numerals_question()
        elif question_type == "Usable IP Addresses of a Subnet":
            question = generate_subnet_usable_question()
        elif question_type == "Network and Broadcast Address of a Subnet":
            question = generate_subnet_net_broadcast_question()

        question_msg = {
            "message_type": "QUESTION",
            "question": question,
            "question_number": i + 1,
            "time_limit": cfg["question_seconds"]
        }
        send_to_all_clients(clients, question_msg)
        time.sleep(cfg["question_interval_seconds"])

# Function to verify the client's answer
def verify_answer(client, answer, correct_answer):
    if answer == correct_answer:
        client["score"] += 1
        return {"message_type": "RESULT", "result": "correct", "feedback": cfg["correct_answer"]}
    else:
        return {"message_type": "RESULT", "result": "incorrect", "feedback": cfg["incorrect_answer"]}

# Function to send the leaderboard to all clients
def send_leaderboard(clients):
    sorted_clients = sorted(clients, key=lambda x: x["score"], reverse=True)
    leaderboard = [{"username": c["username"], "score": c["score"]} for c in sorted_clients]
    leaderboard_msg = {"message_type": "LEADERBOARD", "leaderboard": leaderboard}
    send_to_all_clients(clients, leaderboard_msg)

# Function to send the final results after the game ends
def send_final_results(clients):
    sorted_clients = sorted(clients, key=lambda x: x["score"], reverse=True)
    winners = [c["username"] for c in sorted_clients if c["score"] == sorted_clients[0]["score"]]
    if len(winners) == 1:
        result_msg = {"message_type": "FINISHED", "winner": winners[0]}
    else:
        result_msg = {"message_type": "FINISHED", "winners": winners}
    send_to_all_clients(clients, result_msg)

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--config")
    ap.add_argument("maybe_config", nargs="?", default=None)
    args = ap.parse_args()
    cfg_path = args.config or args.maybe_config
    cfg = load_config(cfg_path)

    port = cfg["port"]
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen()
    except OSError:
        die(f"server.py: Binding to port {port} was unsuccessful")

    players_needed = cfg["players"]
    clients = []
    while True:
        conn, addr = srv.accept()
        data = conn.recv(65536)
        try:
            msg = json.loads(data.decode("utf-8"))
        except Exception:
            conn.close()
            continue
        
        if msg.get("message_type") == "HI":
            username = msg.get("username", "")

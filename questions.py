# questions.py — minimal generators used by server

import random

def generate_mathematics_question() -> str:
    """
    Return a simple infix expression using 2–5 integers (1–10) and + - * /.
    We separate tokens with spaces so the server/client split() works.
    """
    count = random.randint(2, 5)
    nums = [str(random.randint(1, 10)) for _ in range(count)]
    # Heavily weight + and -, occasionally * or /
    ops_pool = ["+"] * 4 + ["-"] * 4 + ["*"] + ["/"]
    ops = random.choices(ops_pool, k=count - 1)
    parts = []
    for i, n in enumerate(nums):
        parts.append(n)
        if i < len(ops):
            parts.append(ops[i])
    return " ".join(parts)

def int_to_roman(n: int) -> str:
    """Helper: convert 1..3999 to Roman numerals (uppercase)."""
    table = [
        ("M", 1000), ("CM", 900), ("D", 500), ("CD", 400),
        ("C", 100),  ("XC", 90),  ("L", 50),  ("XL", 40),
        ("X", 10),   ("IX", 9),   ("V", 5),   ("IV", 4),
        ("I", 1)
    ]
    out = []
    for sym, val in table:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)

def generate_roman_numerals_question() -> str:
    """
    Return a sentence like 'What is the decimal value of MCMXCIV?'
    The server extracts the last token (the numeral), strips punctuation,
    and computes the answer.
    """
    n = random.randint(1, 3999)
    numeral = int_to_roman(n)
    return f"What is the decimal value of {numeral}?"

def generate_usable_addresses_question() -> str:
    """
    Return a CIDR like '192.168.X.Y/24' for the 'Usable IP Addresses...' type.
    The server expects just the CIDR string (no extra words).
    """
    return f"192.168.{random.randint(0,255)}.{random.randint(0,255)}/24"

def generate_network_broadcast_question() -> str:
    """
    Return a CIDR like '192.168.X.Y/24' for the
    'Network and Broadcast Address...' type. Same format.
    """
    return f"192.168.{random.randint(0,255)}.{random.randint(0,255)}/24"

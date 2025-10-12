# questions.py (fixed & spec-compliant)
import random

# --------------------------------------------------------
# Mathematics
# --------------------------------------------------------
def generate_mathematics_question() -> str:
    """
    Generate a random math expression with 2–5 integers (1–10).
    Operators are weighted to prefer + and -; occasionally * or /.
    Example: '3 + 5 - 2 * 4'
    """
    num_count = random.randint(2, 5)
    numbers = [str(random.randint(1, 10)) for _ in range(num_count)]
    ops_pool = ["+"] * 4 + ["-"] * 4 + ["*"] + ["/"]  # bias toward + and -
    ops = random.choices(ops_pool, k=num_count - 1)
    expr_parts = []
    for i in range(num_count):
        expr_parts.append(numbers[i])
        if i < len(ops):
            expr_parts.append(ops[i])
    return " ".join(expr_parts)


# --------------------------------------------------------
# Roman Numerals
# --------------------------------------------------------
def int_to_roman(n: int) -> str:
    """Convert integer 1–3999 to a Roman numeral."""
    roman = [
        ("I", 1), ("IV", 4), ("V", 5), ("IX", 9),
        ("X", 10), ("XL", 40), ("L", 50), ("XC", 90),
        ("C", 100), ("CD", 400), ("D", 500), ("CM", 900),
        ("M", 1000),
    ]
    out = []
    for sym, val in reversed(roman):
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def generate_roman_numerals_question() -> str:
    """
    Return a full-sentence Roman numeral question, e.g.:
    'What is the decimal value of XLII?'
    """
    n = random.randint(1, 3999)
    return f"What is the decimal value of {int_to_roman(n)}?"


# --------------------------------------------------------
# Usable IP Addresses of a Subnet
# --------------------------------------------------------
def generate_usable_addresses_question() -> str:
    """
    Return a CIDR string for 'usable IP count' questions.
    Spec expects just the subnet (no prose), e.g. '192.168.10.23/24'.
    """
    return f"192.168.{random.randint(0,255)}.{random.randint(0,255)}/24"


# --------------------------------------------------------
# Network and Broadcast Address of a Subnet
# --------------------------------------------------------
def generate_network_broadcast_question() -> str:
    """
    Return a CIDR string for 'network & broadcast' questions.
    Spec expects just the subnet (no prose), e.g. '192.168.55.7/24'.
    """
    return f"192.168.{random.randint(0,255)}.{random.randint(0,255)}/24"


# --------------------------------------------------------
# Compatibility aliases
# --------------------------------------------------------
# These alias names ensure compatibility with both your server.py
# and the official autograder.
generate_subnet_usable_question = generate_usable_addresses_question
generate_subnet_net_broadcast_question = generate_network_broadcast_question

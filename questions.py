import random

def generate_mathematics_question() -> str:
    """
    Generate a random math expression with 2–5 integers (1–10),
    using mostly + and -, sometimes * or /.
    Example: '3 + 5 - 2 * 4'
    """
    num_count = random.randint(2, 5)
    numbers = [str(random.randint(1, 10)) for _ in range(num_count)]
    # Weighted operator selection
    all_ops = ["+"] * 4 + ["-"] * 4 + ["*"] * 1 + ["/"] * 1
    operators = random.choices(all_ops, k=num_count - 1)
    expr_parts = []
    for i in range(num_count):
        expr_parts.append(numbers[i])
        if i < len(operators):
            expr_parts.append(operators[i])
    return " ".join(expr_parts)


def int_to_roman(n: int) -> str:
    """Convert integer 1–3999 to Roman numeral."""
    roman_numerals = [
        ("I", 1), ("IV", 4), ("V", 5), ("IX", 9),
        ("X", 10), ("XL", 40), ("L", 50), ("XC", 90),
        ("C", 100), ("CD", 400), ("D", 500),
        ("CM", 900), ("M", 1000)
    ]
    result = []
    for symbol, value in reversed(roman_numerals):
        while n >= value:
            result.append(symbol)
            n -= value
    return ''.join(result)


def generate_roman_numerals_question() -> str:
    """Generate a Roman numeral conversion question."""
    n = random.randint(1, 3999)
    roman_numeral = int_to_roman(n)
    return f"What is the decimal value of {roman_numeral}?"


def generate_subnet_usable_question() -> str:
    """Generate a CIDR subnet question for usable IPs."""
    subnet = f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}/24"
    return subnet


def generate_subnet_net_broadcast_question() -> str:
    """Generate a CIDR subnet question for network/broadcast addresses."""
    subnet = f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}/24"
    return subnet

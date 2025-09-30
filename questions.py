import random

def generate_mathematics_question() -> str:
    num_count = random.randint(2, 5)  # Between 2 and 5 numbers
    numbers = [random.randint(1, 10) for _ in range(num_count)]
    operators = random.choices(["+", "-"], k=num_count - 1)
    expression = " ".join(f"{numbers[i]} {operators[i] if i < len(operators) else ''}" for i in range(num_count))
    return expression.strip()

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

def generate_roman_numerals_question() -> str:
    n = random.randint(1, 3999)
    roman_numerals = int_to_roman(n)
    return f"What is the decimal value of {roman_numerals}?"

def generate_subnet_usable_question() -> str:
    subnet = f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}/24"
    return f"How many usable addresses are there in the subnet {subnet}?"

def generate_subnet_net_broadcast_question() -> str:
    subnet = f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}/24"
    return f"What are the network and broadcast addresses of the subnet {subnet}?"

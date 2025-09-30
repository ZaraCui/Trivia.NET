kimport random

# Mathematics: 2–5 operands, + / - more common than * /
def generate_mathematics_question() -> str:
    n = random.randint(2, 5)
    nums = [random.randint(1, 10) for _ in range(n)]
    ops_pool = ["+"] * 4 + ["-"] * 4 + ["*"] + ["/"]  # skewed to +/-
    ops = random.choices(ops_pool, k=n - 1)
    parts = []
    for i in range(n - 1):
        parts.append(str(nums[i]))
        parts.append(ops[i])
    parts.append(str(nums[-1]))
    return " ".join(parts)

# Roman numerals: return the roman literal (server expects a "short_question")
def _int_to_roman(value: int) -> str:
    table = [
        ("M", 1000), ("CM", 900), ("D", 500), ("CD", 400),
        ("C", 100), ("XC", 90), ("L", 50), ("XL", 40),
        ("X", 10), ("IX", 9), ("V", 5), ("IV", 4), ("I", 1),
    ]
    out = []
    n = value
    for sym, val in table:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)

def generate_roman_numerals_question() -> str:
    return _int_to_roman(random.randint(1, 3999))

# Subnet helpers
def _rand_cidr() -> str:
    return f"192.168.{random.randint(0,255)}.{random.randint(0,255)}/{random.choice([24,25,26,27,28,29,30])}"

def generate_subnet_usable_question() -> str:
    # e.g. "192.168.1.0/24"
    return _rand_cidr()

def generate_subnet_net_broadcast_question() -> str:
    # e.g. "192.168.1.37/24"
    return _rand_cidr()


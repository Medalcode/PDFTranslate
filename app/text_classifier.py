"""
Text block classifier.
Detects whether a PDF text block is: code, a title, or regular paragraph text.
"""

CODE_PATTERNS = [
    "def ",
    "import ",
    "from ",
    "class ",
    "return ",
    "print(",
    "if ",
    "else:",
    "elif ",
    "for ",
    "while ",
    "try:",
    "except",
    "with ",
    "lambda",
    "pip install",
    "pip ",
    "sudo ",
    "apt ",
    "npm ",
    "yarn ",
    "git ",
    "docker",
    "SELECT ",
    "FROM ",
    "WHERE ",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "CREATE ",
    "#!/",
    "http://",
    "https://",
    "$ ",
    ">>> ",
    "...",
]

# Symbols that strongly indicate code
CODE_SYMBOLS = ["{", "}", "=>", "->", "==", "!=", ">=", "<=", "++", "--", "&&", "||"]


def is_code(text: str) -> bool:
    """Returns True if the text block looks like source code or a command."""
    stripped = text.strip()
    if not stripped:
        return False

    # Check pattern keywords
    for pattern in CODE_PATTERNS:
        if pattern in stripped:
            return True

    # Check code symbols
    symbol_count = sum(1 for sym in CODE_SYMBOLS if sym in stripped)
    if symbol_count >= 2:
        return True

    # High ratio of non-alpha characters is typical of code
    non_alpha = sum(1 for c in stripped if not c.isalpha() and not c.isspace())
    total = len(stripped)
    if total > 10 and non_alpha / total > 0.45:
        return True

    return False


def is_title(text: str) -> bool:
    """Returns True if the text block looks like a chapter title or heading."""
    stripped = text.strip()
    if not stripped:
        return False

    words = stripped.split()
    # Short (≤ 10 words), ends without period, and title-cased or uppercase
    if len(words) <= 10 and not stripped.endswith("."):
        if stripped.isupper() or stripped.istitle():
            return True
    return False


def classify(text: str) -> str:
    """Returns 'code', 'title', or 'text'."""
    if is_code(text):
        return "code"
    if is_title(text):
        return "title"
    return "text"

"""
Text block classifier.
Returns: 'code', 'title', or 'body'.
"""
import re

# Strict code-only patterns — must appear at line start
_CODE_START = re.compile(
    r"""^\s*(
        def\s+\w+\s*\(        # Python function
      | class\s+\w+            # class definition
      | import\s+\w+           # import statement
      | from\s+\w+\s+import    # from import
      | public\s+(class|static|void|int|String)  # Java
      | \$\s+\w+               # shell command
      | >>>\s+                 # Python REPL
      | \#include\s*<          # C/C++ include
      | SELECT\s+|UPDATE\s+|DELETE\s+|INSERT\s+  # SQL
      | pip\s+install          # pip
    )""",
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

_CODE_SYMBOLS = [
    "{", "}", "=>", "->", "==", "!=", ">=", "<=",
    "++", "--", "&&", "||", "::", "/*", "*/",
    "def ", "class ", "return ", "import ", "const ", "let "
]

# Patterns that look like indexing / TOC / page refs (dots + page number)
_TOC_LINE = re.compile(r"\.{3,}")  # three or more consecutive dots

# Match Roman numerals or simple digits often used for pagination
_PAGINATION = re.compile(r"^(?:[ivxlcdm]+|\d+)\s*$", re.IGNORECASE)


def is_code(text: str) -> bool:
    """Return True only if the block is clearly source code or a shell command."""
    stripped = text.strip()
    if not stripped:
        return False

    # Table-of-contents dot leaders and pagination: never code
    if _TOC_LINE.search(stripped) or _PAGINATION.match(stripped):
        return False

    # Strong keyword match at line start
    if _CODE_START.search(stripped):
        return True

    # Count code-specific symbol pairs
    symbol_hits = sum(1 for sym in _CODE_SYMBOLS if sym in stripped)
    if symbol_hits >= 2:
        return True

    # High ratio of non-alpha chars — but only if the block is short
    # (long prose can have punctuation; real code blocks tend to be short and dense)
    non_alpha = sum(1 for c in stripped if not c.isalpha() and not c.isspace())
    total = len(stripped)
    if total > 0:
        ratio = non_alpha / total
        # Short, dense with punctuation → likely code
        if total <= 120 and ratio > 0.55:
            return True
        # Long blocks are almost never code by this heuristic
        if total > 120 and ratio > 0.70:
            return True

    return False


def is_title(text: str) -> bool:
    """Return True if the block looks like a heading or chapter title."""
    stripped = text.strip()
    if not stripped:
        return False

    # TOC lines and pagination are not real titles — treat as skip/body
    if _TOC_LINE.search(stripped) or _PAGINATION.match(stripped):
        return False

    words = stripped.split()
    # Short — does not end with sentence-closing punctuation
    if len(words) <= 12 and not stripped[-1] in ".,:;?!":
        # Must have mostly capitalized words or be all-caps
        cap_words = sum(1 for w in words if w and w[0].isupper())
        if cap_words / len(words) >= 0.6:
            return True

    return False


def is_skip(text: str) -> bool:
    """Return True if the block is just pagination or TOC leaders that shouldn't be translated."""
    stripped = text.strip()
    return bool(_TOC_LINE.search(stripped) or _PAGINATION.match(stripped))

def classify(text: str) -> str:
    """Classify a PDF text block as 'code', 'title', 'skip', or 'body'."""
    if is_skip(text):
        return "skip"
    if is_code(text):
        return "code"
    if is_title(text):
        return "title"
    return "body"

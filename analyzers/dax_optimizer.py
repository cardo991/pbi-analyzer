"""DAX Optimizer: concrete rewrite engine for measure expressions.

Each rewriter takes a DAX expression and returns an optimized version or None.
Rewriters are applied sequentially — one optimization can chain onto another.
"""

import re


def optimize_measure(expression: str) -> str | None:
    """Apply safe DAX rewrites to a measure expression.

    Returns the optimized expression, or None if no optimization applies.
    """
    if not expression or not expression.strip():
        return None

    result = expression
    changed = False

    for rewriter in _REWRITERS:
        try:
            new_result = rewriter(result)
            if new_result is not None and new_result != result:
                result = new_result
                changed = True
        except Exception:
            continue  # skip failed rewriter, preserve current result

    return result if changed else None


# ---------------------------------------------------------------------------
# Individual rewriters
# ---------------------------------------------------------------------------

def _rewrite_dax002(expr: str) -> str | None:
    """SUMX(T, T[C]) -> SUM(T[C]), AVERAGEX -> AVERAGE, etc."""
    pattern = re.compile(
        r"(?i)\b(SUMX|AVERAGEX|MINX|MAXX)\s*\(\s*"
        r"('?[A-Za-z][\w\s]*'?)\s*,\s*"
        r"\2\s*\[([^\]]+)\]\s*\)",
    )
    alt_map = {"SUMX": "SUM", "AVERAGEX": "AVERAGE", "MINX": "MIN", "MAXX": "MAX"}

    def replacer(m):
        func = m.group(1).upper()
        table = m.group(2).strip()
        col = m.group(3)
        return f"{alt_map.get(func, 'SUM')}({table}[{col}])"

    new_expr = pattern.sub(replacer, expr)
    return new_expr if new_expr != expr else None


def _rewrite_dax004(expr: str) -> str | None:
    """IF(cond, TRUE, FALSE) -> cond."""
    pat = re.compile(
        r"(?i)\bIF\s*\(\s*(.+?)\s*,\s*"
        r"(?:TRUE\s*\(\s*\)|TRUE|1)\s*,\s*"
        r"(?:FALSE\s*\(\s*\)|FALSE|0)\s*\)"
    )
    new_expr = pat.sub(r"\1", expr)
    if new_expr != expr:
        return new_expr

    # IF(cond, FALSE, TRUE) -> NOT(cond)
    pat2 = re.compile(
        r"(?i)\bIF\s*\(\s*(.+?)\s*,\s*"
        r"(?:FALSE\s*\(\s*\)|FALSE|0)\s*,\s*"
        r"(?:TRUE\s*\(\s*\)|TRUE|1)\s*\)"
    )
    new_expr = pat2.sub(r"NOT(\1)", expr)
    return new_expr if new_expr != expr else None


def _rewrite_dax005(expr: str) -> str | None:
    """COUNTROWS(VALUES(T[C])) -> DISTINCTCOUNT(T[C])."""
    pattern = re.compile(
        r"(?i)\bCOUNTROWS\s*\(\s*(?:VALUES|DISTINCT)\s*\("
        r"\s*('?[\w\s]+'?\s*\[[^\]]+\])\s*\)\s*\)"
    )
    new_expr = pattern.sub(r"DISTINCTCOUNT(\1)", expr)
    return new_expr if new_expr != expr else None


def _rewrite_dax009(expr: str) -> str | None:
    """CALCULATE(expr, FILTER(Table, cond)) -> CALCULATE(expr, cond).

    Only when FILTER's first arg is a bare table name (not a sub-expression).
    """
    pattern = re.compile(r"(?i)\bFILTER\s*\(\s*('?[A-Za-z][\w\s]*'?)\s*,\s*")
    match = pattern.search(expr)
    if not match:
        return None

    # Find closing paren of FILTER(...) using balanced counting
    open_pos = expr.index("(", match.start() + 6)
    depth = 1
    i = open_pos + 1
    cond_start = match.end()

    while i < len(expr) and depth > 0:
        if expr[i] == "(":
            depth += 1
        elif expr[i] == ")":
            depth -= 1
        i += 1

    if depth != 0:
        return None

    filter_end = i
    condition = expr[cond_start:filter_end - 1].strip()

    # Don't rewrite if condition contains nested FILTER
    if re.search(r"(?i)\bFILTER\s*\(", condition):
        return None

    new_expr = expr[:match.start()] + condition + expr[filter_end:]
    return new_expr if new_expr != expr else None


def _rewrite_dax010(expr: str) -> str | None:
    """IF(ISBLANK(x), default, x) -> COALESCE(x, default)."""
    pattern = re.compile(r"(?i)\bIF\s*\(\s*ISBLANK\s*\(")
    match = pattern.search(expr)
    if not match:
        return None

    # Find ISBLANK( argument using balanced parens
    # We need: IF( ISBLANK( <x> ) , <default> , <x> )
    if_open = expr.index("(", match.start())
    isblank_open = expr.index("(", if_open + 1)

    # Find closing paren of ISBLANK(...)
    depth = 1
    i = isblank_open + 1
    while i < len(expr) and depth > 0:
        if expr[i] == "(":
            depth += 1
        elif expr[i] == ")":
            depth -= 1
        i += 1

    if depth != 0:
        return None

    isblank_arg = expr[isblank_open + 1:i - 1].strip()

    # After ISBLANK(...) expect: , <default> , <x> )
    rest = expr[i:].lstrip()
    if not rest.startswith(","):
        return None

    # Parse two remaining IF args
    args = _split_if_args(rest[1:])
    if len(args) < 2:
        return None

    default_val = args[0].strip()
    x_val = args[1].strip()

    # Verify third arg matches isblank_arg
    if x_val.lower().replace(" ", "") == isblank_arg.lower().replace(" ", ""):
        replacement = f"COALESCE({isblank_arg}, {default_val})"
        # Find the full IF(...) span to replace
        if_end = _find_closing_paren(expr, if_open)
        if if_end:
            new_expr = expr[:match.start()] + replacement + expr[if_end:]
            return new_expr if new_expr != expr else None

    return None


def _rewrite_dax011(expr: str) -> str | None:
    """a / b -> DIVIDE(a, b, 0). Only single division, not in strings."""
    # Already uses DIVIDE? skip
    if re.search(r"(?i)\bDIVIDE\s*\(", expr):
        return None

    # Find / positions outside strings
    positions = []
    in_string = False
    for idx, ch in enumerate(expr):
        if ch == '"':
            in_string = not in_string
        elif not in_string and ch == "/":
            if idx + 1 < len(expr) and expr[idx + 1] == "/":
                break  # comment
            positions.append(idx)

    if len(positions) != 1:
        return None  # skip 0 or multiple divisions

    pos = positions[0]
    numerator = expr[:pos].rstrip()
    denominator = expr[pos + 1:].lstrip()

    if not numerator or not denominator:
        return None

    return f"DIVIDE({numerator}, {denominator}, 0)"


def _rewrite_dax003(expr: str) -> str | None:
    """Repeated [MeasureRef] -> wrap in VAR/RETURN."""
    if re.search(r"(?i)\bVAR\b", expr):
        return None

    refs = re.findall(r"\[[^\]]{3,}\]", expr)
    freq = {}
    for r in refs:
        freq[r] = freq.get(r, 0) + 1

    repeated = {ref: count for ref, count in freq.items() if count >= 2}
    if not repeated:
        return None

    var_lines = []
    new_body = expr
    for idx, (ref, _count) in enumerate(repeated.items()):
        var_name = f"_val{idx + 1}" if len(repeated) > 1 else "_val"
        var_lines.append(f"VAR {var_name} = {ref}")
        new_body = new_body.replace(ref, var_name)

    return "\n".join(var_lines) + "\nRETURN\n" + new_body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_if_args(text: str) -> list[str]:
    """Split comma-separated IF arguments respecting parentheses."""
    args = []
    depth = 0
    current = []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                if current:
                    args.append("".join(current))
                return args
            depth -= 1
        elif ch == "," and depth == 0:
            args.append("".join(current))
            current = []
            continue
        current.append(ch)
    if current:
        args.append("".join(current))
    return args


def _find_closing_paren(expr: str, open_pos: int) -> int | None:
    """Find the position AFTER the closing paren matching open_pos."""
    depth = 1
    i = open_pos + 1
    while i < len(expr) and depth > 0:
        if expr[i] == "(":
            depth += 1
        elif expr[i] == ")":
            depth -= 1
        i += 1
    return i if depth == 0 else None


# Rewriters in safe-to-apply order (structural last)
_REWRITERS = [
    _rewrite_dax002,
    _rewrite_dax004,
    _rewrite_dax005,
    _rewrite_dax010,
    _rewrite_dax011,
    _rewrite_dax009,
    _rewrite_dax003,  # last: restructures the whole expression
]

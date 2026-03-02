"""DAX Formatter: auto-indent DAX expressions with proper formatting.

Applies rules:
- VAR and RETURN at base indent level
- CALCULATE args on separate indented lines
- Nested function calls increase indent
- Comma-separated args one-per-line when complex
- String literals preserved as-is
"""

import re

INDENT = "    "  # 4 spaces

# DAX keywords that start a new block at base level
_BLOCK_KEYWORDS = {"VAR", "RETURN"}

# Functions whose args should be split onto separate lines
_SPLIT_FUNCTIONS = {
    "CALCULATE", "CALCULATETABLE", "FILTER", "SUMX", "AVERAGEX",
    "COUNTX", "MAXX", "MINX", "RANKX", "ADDCOLUMNS", "SELECTCOLUMNS",
    "SUMMARIZE", "SUMMARIZECOLUMNS", "GENERATE", "GENERATEALL",
    "IF", "SWITCH", "DIVIDE", "COALESCE",
}


def format_dax(expression: str) -> str:
    """Format a DAX expression with proper indentation."""
    if not expression or not expression.strip():
        return expression

    expr = expression.strip()

    # If it's a simple single-function call with no nesting, return as-is
    if _is_simple(expr):
        return expr

    tokens = _tokenize(expr)
    return _format_tokens(tokens)


def _is_simple(expr: str) -> bool:
    """Check if expression is simple enough to not need formatting."""
    # Count non-string parentheses
    depth = 0
    in_string = False
    commas_at_depth_1 = 0
    for ch in expr:
        if ch == '"' and not in_string:
            in_string = True
        elif ch == '"' and in_string:
            in_string = False
        elif not in_string:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ',' and depth == 1:
                commas_at_depth_1 += 1
    # Simple if: no newlines, max 1 nesting level, short, few args
    return '\n' not in expr and depth == 0 and len(expr) < 80 and commas_at_depth_1 <= 2


def _tokenize(expr: str) -> list[dict]:
    """Tokenize DAX expression into meaningful tokens."""
    tokens = []
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]

        # Skip whitespace (but track newlines)
        if ch in (' ', '\t', '\r'):
            i += 1
            continue
        if ch == '\n':
            tokens.append({"type": "newline"})
            i += 1
            continue

        # String literal
        if ch == '"':
            j = i + 1
            while j < n:
                if expr[j] == '"':
                    if j + 1 < n and expr[j + 1] == '"':
                        j += 2  # escaped quote
                    else:
                        j += 1
                        break
                else:
                    j += 1
            tokens.append({"type": "string", "value": expr[i:j]})
            i = j
            continue

        # Column reference [Table[Column]] or [Measure Name]
        if ch == '[':
            j = i + 1
            bracket_depth = 1
            while j < n and bracket_depth > 0:
                if expr[j] == '[':
                    bracket_depth += 1
                elif expr[j] == ']':
                    bracket_depth -= 1
                j += 1
            tokens.append({"type": "reference", "value": expr[i:j]})
            i = j
            continue

        # Table reference 'Table Name'
        if ch == "'":
            j = i + 1
            while j < n and expr[j] != "'":
                j += 1
            j += 1  # include closing quote
            tokens.append({"type": "reference", "value": expr[i:j]})
            i = j
            continue

        # Parentheses
        if ch == '(':
            tokens.append({"type": "lparen"})
            i += 1
            continue
        if ch == ')':
            tokens.append({"type": "rparen"})
            i += 1
            continue

        # Comma
        if ch == ',':
            tokens.append({"type": "comma"})
            i += 1
            continue

        # Operators
        if ch in ('=', '<', '>', '!', '+', '-', '*', '/', '&', '|'):
            op = ch
            if i + 1 < n and expr[i + 1] in ('=', '>'):
                op += expr[i + 1]
                i += 1
            tokens.append({"type": "operator", "value": op})
            i += 1
            continue

        # Word (keyword, function name, number, etc.)
        if ch.isalnum() or ch in ('_', '.', '#'):
            j = i
            while j < n and (expr[j].isalnum() or expr[j] in ('_', '.', '#')):
                j += 1
            word = expr[i:j]
            tokens.append({"type": "word", "value": word})
            i = j
            continue

        # Anything else (keep as-is)
        tokens.append({"type": "other", "value": ch})
        i += 1

    return tokens


def _format_tokens(tokens: list[dict]) -> str:
    """Format tokenized DAX into properly indented string."""
    lines = []
    current_line = []
    indent_level = 0
    paren_depth = 0
    # Track function name at each paren depth to know if we should split args
    func_stack = []
    should_split_stack = []

    def flush_line():
        if current_line:
            text = "".join(current_line).strip()
            if text:
                lines.append(INDENT * indent_level + text)
            current_line.clear()

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok["type"] == "newline":
            # Existing newlines in VAR/RETURN blocks
            i += 1
            continue

        if tok["type"] == "word" and tok["value"].upper() in _BLOCK_KEYWORDS:
            flush_line()
            keyword = tok["value"].upper()
            if keyword == "VAR":
                indent_level = 0
                current_line.append("VAR ")
                # Collect the rest of the VAR assignment
                i += 1
                while i < len(tokens):
                    t = tokens[i]
                    if t["type"] == "word" and t["value"].upper() in _BLOCK_KEYWORDS:
                        break
                    if t["type"] == "operator":
                        current_line.append(f" {t['value']} ")
                    elif t["type"] == "comma":
                        current_line.append(", ")
                    else:
                        current_line.append(_token_str(t))
                    if t["type"] == "lparen":
                        paren_depth += 1
                        func_stack.append("")
                        should_split_stack.append(False)
                    elif t["type"] == "rparen":
                        paren_depth = max(0, paren_depth - 1)
                        if func_stack:
                            func_stack.pop()
                        if should_split_stack:
                            should_split_stack.pop()
                    i += 1
                flush_line()
                continue
            elif keyword == "RETURN":
                indent_level = 0
                current_line.append("RETURN")
                flush_line()
                indent_level = 1
                i += 1
                continue

        if tok["type"] == "word" and tok["value"].upper() in _SPLIT_FUNCTIONS:
            func_name = tok["value"].upper()
            current_line.append(tok["value"])
            # Look ahead for lparen
            if i + 1 < len(tokens) and tokens[i + 1]["type"] == "lparen":
                current_line.append("(")
                i += 2
                paren_depth += 1
                func_stack.append(func_name)
                # Count args at this level to decide if we should split
                arg_count = _count_args_at_level(tokens, i)
                should_split = arg_count > 1
                should_split_stack.append(should_split)
                if should_split:
                    flush_line()
                    indent_level += 1
                continue
            i += 1
            continue

        if tok["type"] == "lparen":
            current_line.append("(")
            paren_depth += 1
            func_stack.append("")
            should_split_stack.append(False)
            i += 1
            continue

        if tok["type"] == "rparen":
            should_split = should_split_stack[-1] if should_split_stack else False
            if should_split:
                flush_line()
                indent_level = max(0, indent_level - 1)
                current_line.append(")")
            else:
                current_line.append(")")
            paren_depth = max(0, paren_depth - 1)
            if func_stack:
                func_stack.pop()
            if should_split_stack:
                should_split_stack.pop()
            i += 1
            continue

        if tok["type"] == "comma":
            current_line.append(",")
            should_split = should_split_stack[-1] if should_split_stack else False
            if should_split:
                flush_line()
            else:
                current_line.append(" ")
            i += 1
            continue

        if tok["type"] == "operator":
            current_line.append(f" {tok['value']} ")
            i += 1
            continue

        current_line.append(_token_str(tok))
        i += 1

    flush_line()

    # Clean up: remove excessive blank lines, fix spacing
    result = "\n".join(lines)
    result = re.sub(r" +\n", "\n", result)  # trailing spaces
    result = re.sub(r"\n{3,}", "\n\n", result)  # excessive blank lines
    return result


def _token_str(tok: dict) -> str:
    """Get string representation of a token."""
    if tok["type"] in ("word", "string", "reference", "operator", "other"):
        return tok["value"]
    if tok["type"] == "lparen":
        return "("
    if tok["type"] == "rparen":
        return ")"
    if tok["type"] == "comma":
        return ","
    return ""


def _count_args_at_level(tokens: list[dict], start: int) -> int:
    """Count arguments at the current parenthesis level starting from start."""
    depth = 0
    count = 1
    for i in range(start, len(tokens)):
        tok = tokens[i]
        if tok["type"] == "lparen":
            depth += 1
        elif tok["type"] == "rparen":
            if depth == 0:
                return count
            depth -= 1
        elif tok["type"] == "comma" and depth == 0:
            count += 1
    return count

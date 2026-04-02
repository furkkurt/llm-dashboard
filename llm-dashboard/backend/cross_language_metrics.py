"""
Cross-language code metrics aligned with metrics.md.

Computed from raw source text using heuristic token/structure analysis so both
Kotlin and Dart/Flutter snippets are handled without extra tool outputs.
Values are research proxies, not compiler-grade measurements.
"""

from __future__ import annotations

import math
import re
from typing import Any

# Decision points (McCabe-style, file-level)
_DECISION_RE = re.compile(
    r"\b(if|else|while|for|when|catch|case)\b|\|\||&&|\?[^\n:]*:",
    re.MULTILINE,
)
_FUN_KOTLIN = re.compile(r"\bfun\s+[A-Za-z_][\w]*")
_DART_FN = re.compile(
    r"\b(void|Future\s*<[^>]+>|int|double|num|String|bool|Widget|Iterable\s*<[^>]+>)\s+"
    r"[A-Za-z_][\w]*\s*\(",
    re.MULTILINE,
)


def _strip_block_comments(s: str) -> str:
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        if i + 1 < n and s[i : i + 2] == "/*":
            j = s.find("*/", i + 2)
            if j == -1:
                break
            out.append(" ")
            i = j + 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _strip_line_comments(s: str) -> str:
    lines = []
    for line in s.splitlines():
        in_str = False
        quote = ""
        i = 0
        cut = len(line)
        while i < len(line):
            c = line[i]
            if not in_str:
                if c in "\"'":
                    in_str = True
                    quote = c
                elif i + 1 < len(line) and line[i : i + 2] == "//":
                    cut = i
                    break
            else:
                if c == quote and (i == 0 or line[i - 1] != "\\"):
                    in_str = False
                    quote = ""
            i += 1
        lines.append(line[:cut])
    return "\n".join(lines)


def _rough_strip_strings(s: str) -> str:
    """Replace string literals with spaces to avoid counting braces/keywords inside."""
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'":
            q = c
            out.append(" ")
            i += 1
            if i < n and s[i] == q and q == c:
                # raw """ or ''' — advance to triple end
                if i + 1 < n and s[i + 1] == q:
                    end = s.find(q * 3, i + 2)
                    if end == -1:
                        break
                    i = end + 3
                    continue
            while i < n:
                if s[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _comment_and_code_lines(code: str) -> tuple[int, int, int]:
    """
    Returns (comment_line_count, code_line_count, total_non_empty_lines).
    A line is a 'comment line' if, after stripping // and trimming, it is empty
    and was only a comment, or contains only block-comment residue (heuristic).
    """
    no_block = _strip_block_comments(code)
    no_line = _strip_line_comments(no_block)
    total_nonempty = 0
    comment_only = 0
    code_lines = 0
    for raw, stripped in zip(no_block.splitlines(), no_line.splitlines()):
        t = raw.strip()
        if not t:
            continue
        total_nonempty += 1
        if not stripped.strip():
            comment_only += 1
        else:
            code_lines += 1
    return comment_only, code_lines, max(1, total_nonempty)


def _function_count(text: str) -> int:
    fk = len(_FUN_KOTLIN.findall(text))
    fd = len(_DART_FN.findall(text))
    n = fk + fd
    return max(1, n)


def _cyclomatic_total(text: str) -> int:
    # Base 1 + each decision construct / boolean operator / elvis-style ternary starter
    return 1 + len(_DECISION_RE.findall(text))


def _max_brace_depth(text: str) -> int:
    d = depth = 0
    for c in text:
        if c == "{":
            d += 1
            depth = max(depth, d)
        elif c == "}":
            d = max(0, d - 1)
    return max(depth, 0)


def _halstead_approx(text: str) -> tuple[float, float, int, int, int, int]:
    """
    Lightweight Halstead-style counts from alphanumeric words vs operator symbols.
    Returns (volume, difficulty, n1, n2, N1, N2).
    """
    words = re.findall(r"[A-Za-z_][\w]*", text)
    ops_tok = re.findall(r"[+\-*/%=<>!&|^~?:]+|&&|\|\|", text)
    singles = re.findall(r"[;,.()\[\]{}]", text)
    operands = [w for w in words if w not in _KEYWORDS_SKIP]
    op_list = ops_tok + singles

    n1 = len(set(op_list))
    n2 = len(set(operands))
    N1 = len(op_list)
    N2 = len(operands)
    n = n1 + n2
    N = N1 + N2
    if n <= 0 or N <= 0:
        return 0.0, 0.0, n1, n2, N1, N2
    volume = float(N * math.log2(n))
    difficulty = float((n1 / 2.0) * (N2 / max(n2, 1)))
    return volume, difficulty, n1, n2, N1, N2


_KEYWORDS_SKIP = frozenset(
    """
    if else for while do when try catch finally return break continue
    in is as class interface object fun val var const let true false null
    void new this super import export package public private protected
    static final abstract extension mixin typedef await async yield
    required factory get set external dynamic typedef covariant
    """.split()
)


def _maintainability_index(
    volume: float,
    cyclomatic: float,
    loc: int,
    per_cm_percent: float,
) -> float:
    """metrics.md formula (Microsoft-style MI)."""
    v = max(volume, 1e-6)
    cc = max(cyclomatic, 1.0)
    line_count = max(loc, 1)
    per_cm = max(0.0, min(100.0, per_cm_percent))
    try:
        mi = (
            171.0
            - 5.2 * math.log(v)
            - 0.23 * cc
            - 16.2 * math.log(line_count)
            + 50.0 * math.sin(math.sqrt(2.4 * per_cm))
        )
    except (ValueError, OverflowError):
        mi = 0.0
    return float(mi)


def compute_cross_language_metrics(code: str) -> dict[str, Any]:
    """Returns metrics.md / metricguide.md field names: loc, comment_lines, comment_ratio, etc."""
    empty = {
        "loc": None,
        "comment_lines": None,
        "code_lines": None,
        "avg_cyclomatic_complexity": None,
        "comment_ratio": None,
        "halstead_volume": None,
        "halstead_difficulty": None,
        "maintainability_index": None,
        "avg_nesting_depth": None,
    }
    if not (code or "").strip():
        return empty

    no_comments = _strip_line_comments(_strip_block_comments(code))
    logic = _rough_strip_strings(no_comments)

    comment_lines, code_lines, _ = _comment_and_code_lines(code)
    # metrics.md: LOC = raw line count; comment ratio = comment_lines / total_lines
    total_phys = len(code.splitlines())
    if total_phys == 0:
        total_phys = 1
    loc = int(total_phys)
    comment_ratio = float(comment_lines) / float(max(loc, 1))

    fn = _function_count(logic)
    cc_total = _cyclomatic_total(logic)
    avg_cc = float(cc_total) / float(fn)

    nest_max = float(_max_brace_depth(logic))
    # metrics.md: average max depth per function — proxy: max file depth / fn
    avg_nest = nest_max / float(fn)

    vol, diff, _, _, _, _ = _halstead_approx(logic)
    loc_for_mi = max(code_lines, 1)
    per_cm = 100.0 * float(comment_lines) / float(max(loc, 1))
    mi = _maintainability_index(vol, float(cc_total), loc_for_mi, per_cm)

    return {
        "loc": loc,
        "comment_lines": int(comment_lines),
        "code_lines": int(code_lines),
        "avg_cyclomatic_complexity": round(avg_cc, 3),
        "comment_ratio": round(comment_ratio, 4),
        "halstead_volume": round(vol, 2),
        "halstead_difficulty": round(diff, 2),
        "maintainability_index": round(mi, 2),
        "avg_nesting_depth": round(avg_nest, 3),
    }

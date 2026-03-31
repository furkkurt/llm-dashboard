"""Extract Dart + pubspec from LLM markdown pastes; build a minimal Flutter package."""

import re
from typing import Optional

from backend.models import ErrorItem

# Common package: import path segment -> pubspec dependency line (version constraint)
PACKAGE_FROM_IMPORT: dict[str, str] = {
    "shared_preferences": "shared_preferences: ^2.2.3",
    "provider": "provider: ^6.1.2",
    "http": "http: ^1.2.0",
    "dio": "dio: ^5.4.0",
    "go_router": "go_router: ^14.0.0",
    "riverpod": "flutter_riverpod: ^2.5.1",
    "flutter_riverpod": "flutter_riverpod: ^2.5.1",
    "hooks_riverpod": "hooks_riverpod: ^2.5.1",
    "camera": "camera: ^0.11.0",
    "image_picker": "image_picker: ^1.0.7",
    "path_provider": "path_provider: ^2.1.2",
    "sqflite": "sqflite: ^2.3.2",
    "intl": "intl: ^0.19.0",
    "uuid": "uuid: ^4.3.3",
    "cupertino_icons": "cupertino_icons: ^1.0.8",
}

_IMPORT_PKG = re.compile(r"""import\s+['"]package:([^/'"]+)/""")

# Optional newline after fence tag (chat / copy-paste friendly)
_FENCE_DART = re.compile(r"```(?:dart)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_FENCE_ANY = re.compile(r"```\s*\n?(.*?)```", re.DOTALL)
_FENCE_YAML = re.compile(r"```(?:ya?ml)\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)

# [8:07 PM, 3/31/2026] Name: message
_LINE_CHAT_PREFIX = re.compile(r"^\s*\[[^\]\n]{1,120}\]\s*[^:]+:\s*")

# PROMPT:/GEMINI:/GPT:/CLAUDE: compare sheets (line-start or same-line code)
_COMPARE_LABEL = re.compile(
    r"^\s*(PROMPT|GEMINI|GPT|CLAUDE|CHATGPT|OPENAI)\s*:\s*",
    re.IGNORECASE,
)
_COMPARE_SECTION_HEAD = re.compile(
    r"(?im)^\s*(PROMPT|GEMINI|GPT|CLAUDE|CHATGPT|OPENAI)\s*:\s*$",
)

_DART_SLICE = re.compile(
    r"(^|\n)(\s*(?:import\s+['\"](?:package:flutter/|dart:)|void\s+main\s*\())",
    re.MULTILINE,
)


def _looks_like_pubspec(block: str) -> bool:
    b = block.strip().lower()
    return "dependencies:" in b and ("flutter:" in b or "sdk:" in b)


def extract_embedded_pubspec(raw: str) -> Optional[str]:
    for m in _FENCE_YAML.finditer(raw):
        block = m.group(1).strip()
        if _looks_like_pubspec(block):
            return block
    for m in _FENCE_ANY.finditer(raw):
        block = m.group(1).strip()
        if block.startswith("name:") and _looks_like_pubspec(block):
            return block
    return None


def strip_compare_sheet_and_chat_noise(text: str) -> str:
    """Remove PROMPT:/GEMINI:/… header lines, chat timestamps, inline labels."""
    out: list[str] = []
    for line in text.splitlines():
        if _LINE_CHAT_PREFIX.match(line):
            line = _LINE_CHAT_PREFIX.sub("", line, count=1)
        m = _COMPARE_LABEL.match(line)
        if m:
            rest = line[m.end() :].lstrip()
            if not rest:
                continue
            line = rest
        out.append(line)
    return "\n".join(out).strip()


def slice_from_first_dart_token(text: str) -> str:
    """Drop leading prose (e.g. task description) before first import or void main."""
    m = _DART_SLICE.search(text)
    if not m:
        return text
    return text[m.start(2) :].lstrip()


def split_compare_transcript(raw: str) -> dict[str, str]:
    """
    Split a paste with sections:
      PROMPT: / GEMINI: / GPT: / CLAUDE: (labels on their own lines).

    Returns keys: prompt, gemini, gpt, claude (only present if found).
    """
    raw = raw.strip()
    hits = list(_COMPARE_SECTION_HEAD.finditer(raw))
    if len(hits) < 2:
        return {}
    out: dict[str, str] = {}
    for i, m in enumerate(hits):
        label = m.group(1).upper()
        start = m.end()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(raw)
        body = raw[start:end].strip()
        if label in ("CHATGPT", "OPENAI"):
            label = "GPT"
        if label == "PROMPT":
            out["prompt"] = body
        elif label == "GEMINI":
            out["gemini"] = body
        elif label == "GPT":
            out["gpt"] = body
        elif label == "CLAUDE":
            out["claude"] = body
    return out


def extract_embedded_dart(raw: str) -> str:
    raw = raw.strip()
    blocks = [b.strip() for b in _FENCE_DART.findall(raw)]
    if blocks:
        for b in blocks:
            if "void main" in b or "runApp(" in b:
                return b
        return max(blocks, key=len)

    cleaned = strip_compare_sheet_and_chat_noise(raw)
    blocks = [b.strip() for b in _FENCE_DART.findall(cleaned)]
    if blocks:
        for b in blocks:
            if "void main" in b or "runApp(" in b:
                return b
        return max(blocks, key=len)

    candidate = slice_from_first_dart_token(cleaned)
    if candidate.strip():
        return candidate
    return cleaned


def infer_packages_from_dart(dart: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for m in _IMPORT_PKG.finditer(dart):
        pkg = m.group(1)
        if pkg == "flutter":
            continue
        if pkg in PACKAGE_FROM_IMPORT:
            line = PACKAGE_FROM_IMPORT[pkg]
            name = line.split(":")[0].strip()
            found[name] = line
    return found


DEFAULT_PUBSPEC_HEAD = """name: snippet_eval
description: Temporary Flutter package for LLM code evaluation
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
"""

DEFAULT_PUBSPEC_TAIL = """
flutter:
  uses-material-design: true
"""


def build_pubspec(user_yaml: Optional[str], dart: str) -> str:
    if user_yaml and user_yaml.strip():
        return user_yaml.strip() + "\n"
    extra = infer_packages_from_dart(dart)
    dep_lines = ""
    for name in sorted(extra.keys()):
        dep_lines += f"  {extra[name]}\n"
    return DEFAULT_PUBSPEC_HEAD + dep_lines + DEFAULT_PUBSPEC_TAIL


_MISSING_URI = re.compile(
    r"Target of URI doesn't exist: 'package:([^/'\"]+)/",
    re.IGNORECASE,
)
_MISSING_DEP = re.compile(
    r"The imported package ['\"]([^'\"]+)['\"] isn't a dependency",
)
_COULD_NOT_FIND = re.compile(
    r"could not find package [`']?([\w_]+)",
    re.IGNORECASE,
)


def missing_packages_from_diagnostics(
    stdout: str,
    stderr: str,
    error_log: list[ErrorItem],
) -> list[str]:
    """Package names to try with `dart pub add` from analyzer / pub output."""
    blob = f"{stdout}\n{stderr}\n" + "\n".join(e.message for e in error_log)
    found: set[str] = set()
    for rx in (_MISSING_URI, _MISSING_DEP, _COULD_NOT_FIND):
        for m in rx.finditer(blob):
            name = m.group(1).strip()
            if name and name != "flutter":
                found.add(name)
    return sorted(found)


def prepare_flutter_project(raw_paste: str) -> tuple[str, str, list[str]]:
    """
    Returns (main_dart_source, pubspec_yaml, info_notes_for_ui_or_logs).
    """
    notes: list[str] = []
    dart = extract_embedded_dart(raw_paste)
    user_pub = extract_embedded_pubspec(raw_paste)
    pubspec = build_pubspec(user_pub, dart)
    if user_pub:
        notes.append("Using pubspec.yaml extracted from pasted markdown.")
    elif infer_packages_from_dart(dart):
        notes.append(
            "Inferred pub.dev dependencies from imports; the analyzer will also run "
            "`dart pub add` for missing packages when diagnostics allow. "
            "Prefer pasting the LLM’s full pubspec.yaml for accuracy."
        )
    else:
        notes.append(
            "Using minimal pubspec (flutter only). "
            "If analysis reports missing packages, paste the LLM's pubspec.yaml block too."
        )
    rp = raw_paste.strip()
    if rp != dart and ("```" in raw_paste or "```dart" in raw_paste.lower()):
        notes.append("Stripped markdown fences from pasted code for analysis.")
    if _COMPARE_LABEL.search(rp):
        notes.append("Removed compare-sheet labels (PROMPT:/GEMINI:/GPT:/CLAUDE:) where present.")
    if _LINE_CHAT_PREFIX.search(rp):
        notes.append("Removed chat-style timestamp prefixes from line starts.")
    if (
        rp != dart
        and "import " in dart
        and not ("```" in raw_paste and "```dart" in raw_paste.lower())
        and len(dart) < len(rp)
    ):
        notes.append("Trimmed leading prose before the first import or void main().")
    return dart, pubspec, notes

import json
import re
from pathlib import Path

from backend.models import ErrorItem, StaticFlagItem

_KOTLINC_LINE = re.compile(
    r"^e:\s*(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+)\s+(?P<msg>.+)$"
)


def parse_kotlinc_stderr(stderr: str) -> list[ErrorItem]:
    items: list[ErrorItem] = []
    for line in (stderr or "").splitlines():
        m = _KOTLINC_LINE.match(line.strip())
        if m:
            fp = m.group("file")
            name = Path(fp).name if fp else None
            items.append(
                ErrorItem(
                    tool="kotlinc",
                    severity="error",
                    file=name,
                    line=int(m.group("line")),
                    column=int(m.group("col")),
                    message=m.group("msg").strip(),
                )
            )
    return items


def parse_detekt_json(report_path: Path) -> list[StaticFlagItem]:
    if not report_path.is_file():
        return []
    try:
        data = json.loads(report_path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return []
    findings = data if isinstance(data, list) else data.get("findings") or []
    out: list[StaticFlagItem] = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        loc = f.get("location") or {}
        path = loc.get("path") or f.get("file")
        name = Path(str(path)).name if path else None
        line = loc.get("source") or {}
        ln = line.get("line") if isinstance(line, dict) else loc.get("line")
        out.append(
            StaticFlagItem(
                tool="detekt",
                rule=f.get("id") or f.get("rule"),
                severity=str(f.get("severity") or "warning").lower(),
                message=str(f.get("message") or f.get("description") or ""),
                file=name,
                line=int(ln) if ln is not None else None,
            )
        )
    return out


def parse_dart_machine_line(line: str) -> tuple[ErrorItem | None, StaticFlagItem | None]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None, None
    parts = line.split("|")
    if len(parts) < 8:
        return None, None
    severity, _typ, code, path, ln_s, col_s, _length, message = parts[:8]
    name = Path(path).name if path else None
    line_n = int(ln_s) if ln_s.isdigit() else None
    col_n = int(col_s) if col_s.isdigit() else None
    sev = severity.lower()
    if sev == "error":
        return (
            ErrorItem(
                tool="dart_analyze",
                severity="error",
                file=name,
                line=line_n,
                column=col_n,
                message=message or code,
            ),
            None,
        )
    return None, StaticFlagItem(
        tool="dart_analyze",
        rule=code or None,
        severity=sev or "info",
        message=message or code,
        file=name,
        line=line_n,
    )


def parse_dart_machine_output(stdout: str) -> tuple[list[ErrorItem], list[StaticFlagItem]]:
    errors: list[ErrorItem] = []
    flags: list[StaticFlagItem] = []
    for line in (stdout or "").splitlines():
        e, f = parse_dart_machine_line(line)
        if e:
            errors.append(e)
        if f:
            flags.append(f)
    return errors, flags

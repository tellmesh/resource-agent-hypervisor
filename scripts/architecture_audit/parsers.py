from __future__ import annotations

import re
from pathlib import Path

from architecture_audit.areas import area_for_path, normalize_path
from architecture_audit.models import DupFragment, DupGroup, ModuleEntry


def parse_inline_list(line: str) -> list[str]:
    if ":" not in line:
        return []
    return [part.strip() for part in line.split(":", 1)[1].split(";") if part.strip()]


def parse_map(path: Path) -> tuple[dict[str, object], list[ModuleEntry], list[str], list[str]]:
    header: dict[str, object] = {}
    modules: list[ModuleEntry] = []
    alerts: list[str] = []
    hotspots: list[str] = []
    in_modules = False

    header_re = re.compile(
        r"^#\s+\S+\s+\|\s+(?P<files>\d+)f\s+(?P<lines>\d+)L.*\|\s+"
        r"(?P<date>\d{4}-\d{2}-\d{2})"
    )
    stats_re = re.compile(
        r"^# stats:\s+(?P<functions>\d+)\s+func\s+\|\s+(?P<classes>\d+)\s+cls\s+\|\s+"
        r"(?P<modules>\d+)\s+mod\s+\|\s+CC.\s*=\s*(?P<cc>[0-9.]+)\s+\|\s+"
        r"critical:(?P<critical>\d+)\s+\|\s+cycles:(?P<cycles>\d+)"
    )

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip()
        if match := header_re.match(line):
            header.update(
                {
                    "files": int(match.group("files")),
                    "lines": int(match.group("lines")),
                    "generated_date": match.group("date"),
                }
            )
        elif match := stats_re.match(line):
            header.update(
                {
                    "functions": int(match.group("functions")),
                    "classes": int(match.group("classes")),
                    "modules": int(match.group("modules")),
                    "cc_avg": float(match.group("cc")),
                    "critical": int(match.group("critical")),
                    "cycles": int(match.group("cycles")),
                }
            )
        elif line.startswith("# alerts"):
            alerts = parse_inline_list(line)
        elif line.startswith("# hotspots"):
            hotspots = parse_inline_list(line)
        elif re.match(r"^M\[\d+\]:", line):
            in_modules = True
        elif line == "D:":
            in_modules = False
        elif in_modules and line.startswith("  "):
            item = line.strip()
            if "," not in item:
                continue
            module_path, raw_lines = item.rsplit(",", 1)
            if raw_lines.isdigit():
                modules.append(
                    ModuleEntry(
                        path=normalize_path(module_path),
                        lines=int(raw_lines),
                        area=area_for_path(module_path),
                    )
                )

    return header, modules, alerts, hotspots


def parse_duplication(path: Path) -> tuple[dict[str, int], list[dict[str, object]], list[DupGroup]]:
    summary: dict[str, int] = {}
    hotspots: list[dict[str, object]] = []
    groups: list[DupGroup] = []
    current: dict[str, object] | None = None
    fragments: list[DupFragment] = []
    in_hotspots = False

    summary_re = re.compile(r"^\s+(?P<key>[a-z_]+):\s+(?P<value>\d+)")
    hotspot_re = re.compile(
        r"^\s+(?P<path>\S+)\s+dup=(?P<dup>\d+)L\s+groups=(?P<groups>\d+)\s+frags=(?P<frags>\d+)"
    )
    group_re = re.compile(
        r"^\s*\[(?P<digest>[^\]]+)\]\s+(?P<flag>!)?\s*(?P<kind>\w+)\s+"
        r"(?P<name>\S+)\s+L=(?P<lines>\d+)\s+N=(?P<count>\d+)\s+"
        r"saved=(?P<saved>\d+)(?:\s+sim=(?P<sim>[0-9.]+))?"
    )
    fragment_re = re.compile(
        r"^\s+(?P<path>.+?):(?P<start>\d+)-(?P<end>\d+)\s+"
        r"\((?P<symbol>[^)]*)\)"
    )

    def flush_group() -> None:
        nonlocal current, fragments
        if current is None:
            return
        groups.append(
            DupGroup(
                digest=str(current["digest"]),
                flagged=bool(current["flagged"]),
                kind=str(current["kind"]),
                name=str(current["name"]),
                lines=int(current["lines"]),
                fragments_count=int(current["fragments_count"]),
                saved_lines=int(current["saved_lines"]),
                similarity=current["similarity"],
                fragments=tuple(fragments),
            )
        )
        current = None
        fragments = []

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip()
        if match := summary_re.match(line):
            summary[match.group("key")] = int(match.group("value"))
            continue
        if line.startswith("HOTSPOTS["):
            in_hotspots = True
            continue
        if line.startswith("DUPLICATES["):
            in_hotspots = False
            continue
        if in_hotspots and (match := hotspot_re.match(line)):
            hot_path = normalize_path(match.group("path"))
            hotspots.append(
                {
                    "path": hot_path,
                    "area": area_for_path(hot_path),
                    "duplicated_lines": int(match.group("dup")),
                    "groups": int(match.group("groups")),
                    "fragments": int(match.group("frags")),
                }
            )
            continue
        if match := group_re.match(line):
            flush_group()
            current = {
                "digest": match.group("digest"),
                "flagged": bool(match.group("flag")),
                "kind": match.group("kind"),
                "name": match.group("name"),
                "lines": int(match.group("lines")),
                "fragments_count": int(match.group("count")),
                "saved_lines": int(match.group("saved")),
                "similarity": float(match.group("sim")) if match.group("sim") else None,
            }
            continue
        if current and (match := fragment_re.match(line)):
            frag_path = normalize_path(match.group("path"))
            fragments.append(
                DupFragment(
                    path=frag_path,
                    start=int(match.group("start")),
                    end=int(match.group("end")),
                    symbol=match.group("symbol"),
                    area=area_for_path(frag_path),
                )
            )

    flush_group()
    return summary, hotspots, groups

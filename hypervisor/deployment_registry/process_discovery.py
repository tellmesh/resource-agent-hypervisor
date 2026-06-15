from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Any


def _iter_proc_pids() -> list[int]:
    proc = Path("/proc")
    if not proc.exists():
        return []
    pids: list[int] = []
    for child in proc.iterdir():
        if child.name.isdigit():
            pids.append(int(child.name))
    return pids


def _listening_socket_inodes(port: int) -> set[str]:
    inodes: set[str] = set()
    for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        if not table.exists():
            continue
        try:
            lines = table.read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 10 or fields[3] != "0A":
                continue
            local = fields[1]
            try:
                local_port = int(local.rsplit(":", 1)[1], 16)
            except (IndexError, ValueError):
                continue
            if local_port == port:
                inodes.add(fields[9])
    return inodes


def pids_listening_on_port(port: int) -> set[int]:
    """Return Linux process IDs listening on a TCP port without requiring lsof/psutil."""
    inodes = _listening_socket_inodes(port)
    if not inodes:
        return set()
    pids: set[int] = set()
    for pid in _iter_proc_pids():
        fd_dir = Path("/proc") / str(pid) / "fd"
        try:
            fds = list(fd_dir.iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if (
                target.startswith("socket:[")
                and target.removeprefix("socket:[").removesuffix("]") in inodes
            ):
                pids.add(pid)
                break
    return pids


def command_line(pid: int) -> str:
    cmdline = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = cmdline.read_bytes()
    except OSError:
        raw = b""
    if raw:
        return " ".join(part.decode("utf-8", "replace") for part in raw.split(b"\0") if part)
    try:
        return (Path("/proc") / str(pid) / "comm").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def command_matches_plan(pid: int, plan: dict[str, Any]) -> bool:
    command = command_line(pid)
    if not command:
        return False
    module = str(plan.get("module") or "")
    if module and module in command:
        return True
    path = str(plan.get("path") or "")
    return bool(path and path in command)


def terminate_pid(pid: int, *, timeout: float = 5.0) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return not _pid_alive(pid)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

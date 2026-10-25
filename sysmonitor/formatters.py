"""Formateo de snapshots a texto legible o JSON (sin I/O)."""

import json
from dataclasses import asdict

from sysmonitor.metrics import Snapshot

BYTES_PER_UNIT = 1024
SIZE_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
JSON_INDENT = 2


def format_bytes(num_bytes: int) -> str:
    """Convierte una cantidad de bytes a una cadena legible.

    Args:
        num_bytes: Cantidad de bytes (>= 0).

    Returns:
        Texto como ``"1.5 GiB"``.
    """
    value = float(num_bytes)
    for unit in SIZE_UNITS[:-1]:
        if value < BYTES_PER_UNIT:
            return f"{value:.1f} {unit}"
        value /= BYTES_PER_UNIT
    return f"{value:.1f} {SIZE_UNITS[-1]}"


def format_text(snapshot: Snapshot) -> str:
    """Genera la salida en texto legible de un snapshot.

    Args:
        snapshot: Lectura de métricas a mostrar.

    Returns:
        Texto multilínea sin salto de línea final.
    """
    mem = snapshot.memory
    net = snapshot.network
    lines = [
        f"CPU: {snapshot.cpu.percent:.1f}%",
        f"RAM: {mem.percent:.1f}% "
        f"({format_bytes(mem.used_bytes)} / {format_bytes(mem.total_bytes)})",
        "Disk:",
    ]
    for disk in snapshot.disks:
        lines.append(
            f"  {disk.mountpoint}: {disk.percent:.1f}% "
            f"({format_bytes(disk.used_bytes)} / {format_bytes(disk.total_bytes)})"
        )
    lines.append(
        f"Network: sent {format_bytes(net.bytes_sent)}, "
        f"received {format_bytes(net.bytes_recv)}"
    )
    return "\n".join(lines)


def format_json(snapshot: Snapshot) -> str:
    """Genera la salida JSON de un snapshot.

    Args:
        snapshot: Lectura de métricas a mostrar.

    Returns:
        Documento JSON válido, apto para ``jq``.
    """
    return json.dumps(asdict(snapshot), indent=JSON_INDENT)

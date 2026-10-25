"""Lectura de métricas del sistema con psutil (solo lectura, sin efectos)."""

import logging
from dataclasses import dataclass

import psutil

CPU_SAMPLE_SECONDS = 1.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CpuMetrics:
    """Uso de CPU.

    Attributes:
        percent: Porcentaje de uso entre 0.0 y 100.0.
    """

    percent: float


@dataclass(frozen=True)
class MemoryMetrics:
    """Uso de memoria RAM.

    Attributes:
        percent: Porcentaje de RAM usada.
        used_bytes: Bytes de RAM usados.
        total_bytes: Bytes de RAM totales.
    """

    percent: float
    used_bytes: int
    total_bytes: int


@dataclass(frozen=True)
class DiskMetrics:
    """Uso de una partición de disco.

    Attributes:
        mountpoint: Punto de montaje de la partición.
        percent: Porcentaje de espacio usado.
        used_bytes: Bytes usados.
        total_bytes: Bytes totales.
    """

    mountpoint: str
    percent: float
    used_bytes: int
    total_bytes: int


@dataclass(frozen=True)
class NetworkMetrics:
    """Contadores de red acumulados desde el arranque del sistema.

    Attributes:
        bytes_sent: Bytes enviados.
        bytes_recv: Bytes recibidos.
    """

    bytes_sent: int
    bytes_recv: int


@dataclass(frozen=True)
class Snapshot:
    """Lectura completa de métricas en un instante.

    Attributes:
        cpu: Métricas de CPU.
        memory: Métricas de RAM.
        disks: Métricas por partición legible.
        network: Contadores de red.
    """

    cpu: CpuMetrics
    memory: MemoryMetrics
    disks: list[DiskMetrics]
    network: NetworkMetrics


def get_cpu(interval: float = CPU_SAMPLE_SECONDS) -> CpuMetrics:
    """Obtiene el porcentaje de uso de CPU.

    Args:
        interval: Segundos de muestreo para calcular el uso.

    Returns:
        Métricas de CPU.
    """
    return CpuMetrics(percent=psutil.cpu_percent(interval=interval))


def get_memory() -> MemoryMetrics:
    """Obtiene el uso de memoria RAM.

    Returns:
        Métricas de RAM.
    """
    mem = psutil.virtual_memory()
    return MemoryMetrics(
        percent=mem.percent, used_bytes=mem.used, total_bytes=mem.total
    )


def get_disks() -> list[DiskMetrics]:
    """Obtiene el uso de cada partición de disco.

    Las particiones que no se pueden leer por falta de permisos se omiten
    con una advertencia; el resto se sigue procesando.

    Returns:
        Lista de métricas, una por partición legible.
    """
    disks: list[DiskMetrics] = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except PermissionError:
            logger.warning(
                "Permission denied reading partition %s; skipping",
                partition.mountpoint,
            )
            continue
        disks.append(
            DiskMetrics(
                mountpoint=partition.mountpoint,
                percent=usage.percent,
                used_bytes=usage.used,
                total_bytes=usage.total,
            )
        )
    return disks


def get_network() -> NetworkMetrics:
    """Obtiene los contadores de red acumulados.

    Returns:
        Bytes enviados y recibidos desde el arranque.
    """
    counters = psutil.net_io_counters()
    return NetworkMetrics(
        bytes_sent=counters.bytes_sent, bytes_recv=counters.bytes_recv
    )


def collect_snapshot() -> Snapshot:
    """Reúne todas las métricas en una sola lectura.

    Returns:
        Snapshot con CPU, RAM, disco y red.
    """
    return Snapshot(
        cpu=get_cpu(),
        memory=get_memory(),
        disks=get_disks(),
        network=get_network(),
    )

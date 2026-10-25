"""Evaluación de umbrales y envío de alertas a webhooks (Slack/Discord)."""

import logging
from dataclasses import dataclass, replace
from urllib.parse import urlparse

import requests

from sysmonitor.metrics import Snapshot

REQUEST_TIMEOUT = 5
SLACK_HOSTS = frozenset({"hooks.slack.com"})
DISCORD_HOSTS = frozenset({"discord.com", "discordapp.com"})
KIND_SLACK = "slack"
KIND_DISCORD = "discord"
KIND_GENERIC = "generic"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Thresholds:
    """Umbrales de alerta en porcentaje.

    Attributes:
        cpu: Umbral de CPU.
        mem: Umbral de RAM.
        disk: Umbral de uso de disco (aplica a cada partición).
    """

    cpu: float
    mem: float
    disk: float


@dataclass(frozen=True)
class Alert:
    """Una alerta o su recuperación.

    Attributes:
        key: Identificador estable de la condición (ej. ``"disk:/"``).
        label: Nombre legible de la métrica.
        value: Porcentaje medido.
        threshold: Umbral que se superó.
        resolved: ``True`` si es un aviso de recuperación.
    """

    key: str
    label: str
    value: float
    threshold: float
    resolved: bool = False

    @property
    def message(self) -> str:
        """Mensaje legible para el usuario o el webhook."""
        if self.resolved:
            return (
                f"[RESOLVED] {self.label} is back below "
                f"{self.threshold:.1f}% threshold"
            )
        return (
            f"[ALERT] {self.label} at {self.value:.1f}% "
            f"(threshold {self.threshold:.1f}%)"
        )


def evaluate(snapshot: Snapshot, thresholds: Thresholds) -> list[Alert]:
    """Devuelve las condiciones que superan su umbral.

    Una métrica alerta solo si es estrictamente mayor que el umbral.

    Args:
        snapshot: Lectura de métricas.
        thresholds: Umbrales configurados.

    Returns:
        Alertas activas en este instante.
    """
    candidates = [
        ("cpu", "CPU", snapshot.cpu.percent, thresholds.cpu),
        ("mem", "RAM", snapshot.memory.percent, thresholds.mem),
    ]
    candidates.extend(
        (f"disk:{d.mountpoint}", f"Disk {d.mountpoint}", d.percent, thresholds.disk)
        for d in snapshot.disks
    )
    return [
        Alert(key, label, value, limit)
        for key, label, value, limit in candidates
        if value > limit
    ]


class AlertTracker:
    """Recuerda qué alertas siguen activas para no repetirlas cada ciclo."""

    def __init__(self) -> None:
        """Crea un tracker sin alertas activas."""
        self._active: dict[str, Alert] = {}

    def update(self, current: list[Alert]) -> list[Alert]:
        """Compara las alertas actuales con las del ciclo anterior.

        Args:
            current: Alertas activas ahora (salida de ``evaluate``).

        Returns:
            Solo las transiciones: alertas nuevas y recuperaciones.
        """
        now = {alert.key: alert for alert in current}
        new = [a for key, a in now.items() if key not in self._active]
        recovered = [
            replace(a, resolved=True)
            for key, a in self._active.items()
            if key not in now
        ]
        self._active = now
        return new + recovered


def detect_webhook_kind(url: str) -> str:
    """Detecta el destino del webhook por el host de la URL.

    Args:
        url: URL del webhook.

    Returns:
        ``"slack"``, ``"discord"`` o ``"generic"``.
    """
    host = urlparse(url).hostname or ""
    if host in SLACK_HOSTS:
        return KIND_SLACK
    if host in DISCORD_HOSTS:
        return KIND_DISCORD
    return KIND_GENERIC


def build_payload(kind: str, message: str) -> dict[str, str]:
    """Construye el cuerpo JSON según el destino.

    Args:
        kind: Resultado de ``detect_webhook_kind``.
        message: Texto de la alerta.

    Returns:
        Diccionario listo para enviarse como JSON.
    """
    if kind == KIND_DISCORD:
        return {"content": message}
    return {"text": message}


def mask_url(url: str) -> str:
    """Oculta la ruta (donde viven los secretos) de una URL de webhook.

    Args:
        url: URL completa.

    Returns:
        Algo como ``https://hooks.slack.com/services/***``.
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.hostname or '?'}/***"


def send_webhook(url: str, message: str) -> bool:
    """Envía un mensaje a un webhook sin propagar errores de red.

    Args:
        url: URL del webhook; debe usar ``https``.
        message: Texto a enviar.

    Returns:
        ``True`` si el servidor aceptó el mensaje, ``False`` en otro caso.
    """
    masked = mask_url(url)
    if urlparse(url).scheme != "https":
        logger.error("Webhook URL must use https: %s", masked)
        return False
    kind = detect_webhook_kind(url)
    if kind == KIND_GENERIC:
        logger.warning(
            "Unknown webhook host in %s; payload format may not be compatible",
            masked,
        )
    try:
        response = requests.post(
            url, json=build_payload(kind, message), timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # Solo el nombre de la clase: str(exc) suele incluir la URL completa.
        logger.error("Webhook delivery to %s failed: %s", masked, type(exc).__name__)
        return False
    logger.debug("Webhook delivered to %s", masked)
    return True

"""Punto de entrada de la CLI: parseo de argumentos y orquestación."""

import argparse
import logging
import sys
import time

from sysmonitor import __version__
from sysmonitor.alerts import AlertTracker, Thresholds, evaluate, send_webhook
from sysmonitor.formatters import format_json, format_text
from sysmonitor.metrics import Snapshot, collect_snapshot

DEFAULT_INTERVAL = 5
DEFAULT_THRESHOLD = 90.0
MIN_PERCENT = 0.0
MAX_PERCENT = 100.0
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

logger = logging.getLogger(__name__)


def percentage(value: str) -> float:
    """Valida que ``value`` sea un porcentaje entre 0 y 100.

    Args:
        value: Texto recibido por la línea de comandos.

    Returns:
        El porcentaje como ``float``.

    Raises:
        argparse.ArgumentTypeError: Si no es un número o está fuera de rango.
    """
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if not MIN_PERCENT <= number <= MAX_PERCENT:
        raise argparse.ArgumentTypeError(
            f"{value} must be between {MIN_PERCENT:g} and {MAX_PERCENT:g}"
        )
    return number


def positive_int(value: str) -> int:
    """Valida que ``value`` sea un entero mayor que cero.

    Args:
        value: Texto recibido por la línea de comandos.

    Returns:
        El entero validado.

    Raises:
        argparse.ArgumentTypeError: Si no es un entero o es <= 0.
    """
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from None
    if number <= 0:
        raise argparse.ArgumentTypeError(f"{value} must be greater than 0")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser de argumentos de la CLI.

    Returns:
        Parser de ``argparse`` configurado.
    """
    parser = argparse.ArgumentParser(
        prog="sysmonitor",
        description="Monitor de CPU, RAM, disco y red con alertas por webhook.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="formato de salida (default: %(default)s)",
    )
    parser.add_argument(
        "--once", action="store_true", help="toma una sola lectura y termina"
    )
    parser.add_argument(
        "--interval",
        type=positive_int,
        default=DEFAULT_INTERVAL,
        help="segundos entre lecturas, mayor que 0 (default: %(default)s)",
    )
    for name, label in (("cpu", "CPU"), ("mem", "RAM"), ("disk", "disco")):
        parser.add_argument(
            f"--{name}-threshold",
            type=percentage,
            default=DEFAULT_THRESHOLD,
            help=f"%% de {label} que dispara alerta, 0-100 (default: %(default)s)",
        )
    parser.add_argument(
        "--webhook",
        default=None,
        help="URL https del webhook (Slack/Discord); sin él no se envían alertas",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="activa logging nivel DEBUG"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def render(snapshot: Snapshot, output_format: str) -> str:
    """Formatea un snapshot según el formato elegido.

    Args:
        snapshot: Lectura de métricas.
        output_format: ``"text"`` o ``"json"``.

    Returns:
        Texto listo para escribirse en stdout.
    """
    if output_format == "json":
        return format_json(snapshot)
    return format_text(snapshot)


def process_alerts(
    snapshot: Snapshot,
    thresholds: Thresholds,
    tracker: AlertTracker,
    webhook: str | None,
) -> None:
    """Evalúa umbrales y notifica solo las transiciones de alerta.

    Cada notificación se registra en stderr; si hay webhook, además se envía.
    Un fallo del webhook lo registra ``send_webhook`` y no detiene nada.

    Args:
        snapshot: Lectura de métricas actual.
        thresholds: Umbrales configurados.
        tracker: Estado de alertas del ciclo anterior.
        webhook: URL del webhook, o ``None`` para no enviar.
    """
    for alert in tracker.update(evaluate(snapshot, thresholds)):
        if alert.resolved:
            logger.info(alert.message)
        else:
            logger.warning(alert.message)
        if webhook is not None:
            send_webhook(webhook, alert.message)


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la herramienta SysMonitor CLI.

    Args:
        argv: Argumentos de línea de comandos; ``None`` usa ``sys.argv``.

    Returns:
        Código de salida: 0 correcto, 1 error, 130 interrumpido.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=LOG_FORMAT,
    )
    thresholds = Thresholds(
        cpu=args.cpu_threshold, mem=args.mem_threshold, disk=args.disk_threshold
    )
    tracker = AlertTracker()
    try:
        while True:
            snapshot = collect_snapshot()
            print(render(snapshot, args.format), flush=True)
            process_alerts(snapshot, thresholds, tracker, args.webhook)
            if args.once:
                return EXIT_OK
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception:
        logger.exception("Unexpected failure")
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())

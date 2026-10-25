# SysMonitor CLI

Herramienta de línea de comandos en Python que monitorea CPU, RAM, disco y red en Linux
y envía alertas a un webhook (Slack o Discord) cuando se superan umbrales configurables.

## Características

- Lectura de CPU (%), RAM (% y usada/total), disco (% por partición) y red (bytes enviados/recibidos).
- Salida en texto legible o JSON válido (apto para `jq`).
- Modo de una lectura (`--once`) o monitoreo continuo con `--interval`.
- Alertas por umbral con anti-spam: se avisa al cruzar el umbral y al recuperarse, no en cada ciclo.
- Un fallo del webhook o una partición ilegible no detienen el monitoreo.

## Requisitos

- Linux (probado en Fedora)
- Python 3.14 o superior
- Dependencias de runtime: `psutil`, `requests`

## Instalación en Fedora

```bash
sudo dnf install -y python3 python3-pip git
git clone <url-del-repositorio>
cd sysmonitor-cli
chmod +x install.sh
./install.sh
source .venv/bin/activate
```

`install.sh` valida la versión de Python, crea `.venv` solo si no existe e instala
`requirements.txt`. Se puede ejecutar varias veces sin problema.

## Uso

```bash
# Ayuda y versión
python -m sysmonitor --help
python -m sysmonitor --version

# Una lectura en texto legible
python -m sysmonitor --once

# Una lectura en JSON
python -m sysmonitor --once --format json | jq .

# Monitoreo continuo cada 10 s con umbrales y alertas por webhook
python -m sysmonitor \
  --interval 10 \
  --cpu-threshold 85 \
  --mem-threshold 90 \
  --disk-threshold 90 \
  --webhook "https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

### Argumentos

| Argumento          | Default | Descripción                                          |
|--------------------|---------|------------------------------------------------------|
| `--format`         | `text`  | `text` o `json`                                      |
| `--once`           | —       | Una sola lectura y termina                           |
| `--interval`       | `5`     | Segundos entre lecturas (> 0)                        |
| `--cpu-threshold`  | `90.0`  | % de CPU que dispara alerta (0–100)                  |
| `--mem-threshold`  | `90.0`  | % de RAM que dispara alerta (0–100)                  |
| `--disk-threshold` | `90.0`  | % de disco que dispara alerta, por partición (0–100) |
| `--webhook`        | —       | URL `https` del webhook; sin él no se envía nada     |
| `-v`, `--verbose`  | —       | Logging nivel DEBUG                                  |
| `--version`        | —       | Muestra la versión y termina                         |

Una métrica alerta cuando es **estrictamente mayor** que su umbral.

### Alertas

- Las alertas siempre se muestran en `stderr`; con `--webhook` además se envían al webhook.
- El destino se detecta por el host: `hooks.slack.com` (Slack), `discord.com` /
  `discordapp.com` (Discord). Otro host recibe un payload genérico y una advertencia.
- La URL del webhook solo se pasa por `--webhook`; nunca se registra completa.

### Flujos de salida y códigos de salida

Los datos van a `stdout`; logs, alertas y errores van a `stderr`, así que
`--format json` se puede canalizar sin ruido.

| Código | Significado                         |
|--------|-------------------------------------|
| `0`    | Ejecución correcta                  |
| `1`    | Error inesperado                    |
| `2`    | Argumentos inválidos                |
| `130`  | Interrumpido con `Ctrl+C`           |

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Las pruebas mockean `psutil` y `requests`: no dependen del hardware ni de la red.

## Estructura

```
sysmonitor/
├── main.py        # argparse y orquestación
├── metrics.py     # lectura de métricas con psutil
├── alerts.py      # umbrales, anti-spam y webhooks
└── formatters.py  # salida en texto y JSON
```

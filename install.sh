#!/usr/bin/env bash
# Instala SysMonitor CLI: valida Python, crea .venv e instala dependencias.
# Idempotente: se puede ejecutar varias veces sin romper nada.
set -euo pipefail

readonly MIN_MAJOR=3
readonly MIN_MINOR=14
readonly VENV_DIR=".venv"
readonly REQUIREMENTS="requirements.txt"

info() { printf '[+] %s\n' "$*"; }
error() { printf '[!] %s\n' "$*" >&2; }

# Trabajar siempre desde la carpeta del script, sin importar desde dónde se llame.
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v python3 >/dev/null 2>&1; then
    error "python3 no está instalado. Instálalo con el gestor de tu distribución:"
    error "  Fedora:          sudo dnf install -y python3 python3-pip"
    error "  Arch Linux:      sudo pacman -S --needed python python-pip"
    error "  Debian/Ubuntu:   sudo apt install -y python3 python3-pip python3-venv"
    exit 1
fi

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (${MIN_MAJOR}, ${MIN_MINOR}) else 1)"; then
    found="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    error "Se requiere Python >= ${MIN_MAJOR}.${MIN_MINOR}; se encontró ${found}."
    exit 1
fi
info "Python $(python3 -c 'import platform; print(platform.python_version())') detectado."

if [[ ! -f "${REQUIREMENTS}" ]]; then
    error "No se encontró ${REQUIREMENTS}."
    exit 1
fi

if [[ -d "${VENV_DIR}" ]]; then
    info "El entorno virtual ${VENV_DIR} ya existe; se reutiliza."
else
    info "Creando entorno virtual en ${VENV_DIR}..."
    if ! python3 -m venv "${VENV_DIR}"; then
        error "No se pudo crear el entorno virtual (¿falta el módulo venv?)."
        error "En Debian/Ubuntu: sudo apt install -y python3-venv"
        exit 1
    fi
fi

info "Instalando dependencias desde ${REQUIREMENTS}..."
"${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip
"${VENV_DIR}/bin/python" -m pip install --quiet -r "${REQUIREMENTS}"

info "Instalación completada."
info "Actívalo con: source ${VENV_DIR}/bin/activate"
info "Pruébalo con: python -m sysmonitor --once"

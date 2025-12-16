#!/usr/bin/env bash
set -e

if ! command -v pipx >/dev/null 2>&1; then
  echo "[+] Installing pipx"
  apt update
  apt install -y pipx
  pipx ensurepath
fi

echo "[+] Installing proxmux"
pipx install proxmux

echo "[+] Done. Run: proxmux --help"
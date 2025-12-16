"""Utility helpers for logging and package manager command mappings.

Provides small convenience wrappers around the logging module for
consistent colored output across the project, and a mapping of common
package manager commands used elsewhere in the codebase.
"""

import logging

# ------------------------
# LOGGING
# ------------------------
# Use a module logger and only configure the root logger if no handlers exist.
logging.basicConfig(level=logging.INFO, format="\033[1;32m[+]\033[0m %(message)s")


def log_warn(msg: str) -> None:
    """Log a warning message with a yellow "[!]" prefix.

    This is a small wrapper around the module logger to keep
    message formatting consistent across the project.
    """
    logging.warning("\033[1;33m[!]\033[0m %s", msg)


def log_info(msg: str) -> None:
    """Log an informational message with a green "[+]" prefix.

    Thin wrapper for consistent project output.
    """
    logging.info("\033[1;32m[+]\033[0m %s", msg)


def log_error(msg: str) -> None:
    """Log an error message with a red "[!]" prefix.

    Thin wrapper around the module logger for consistency.
    """
    logging.error("\033[1;31m[!]\033[0m %s", msg)


PACKAGE_MANAGERS = {
    "apt": {
        "check": "apt",
        "update": "apt update -y && apt upgrade -y",
        "dry_run": "apt update -y && apt list --upgradable",  # ensure cache updated first
    },
    "dnf": {
        "check": "dnf",
        "update": "dnf -y upgrade",
        "dry_run": "dnf check-update",  # dnf check-update refreshes metadata
    },
    "yum": {
        "check": "yum",
        "update": "yum -y update",
        "dry_run": "yum check-update",  # yum check-update refreshes metadata
    },
    "zypper": {
        "check": "zypper",
        "update": "zypper refresh && zypper update -y",
        "dry_run": "zypper refresh && zypper list-updates",  # refresh first
    },
    "pacman": {
        "check": "pacman",
        "update": "pacman -Syu --noconfirm",
        "dry_run": "pacman -Sy && pacman -Qu",  # refresh db first
    },
    "apk": {
        "check": "apk",
        "update": "apk update && apk upgrade",
        "dry_run": "apk update && apk version -l '<'",  # update db first
    },
}

import logging

# ------------------------
# LOGGING
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="\033[1;32m[+]\033[0m %(message)s"
)
log_warn = lambda msg: logging.warning(f"\033[1;33m[!]\033[0m {msg}")
log_info = lambda msg: logging.info(msg)
log_error = lambda msg: logging.error(f"\033[1;31m[!]\033[0m {msg}")

PACKAGE_MANAGERS = {
    "apt": {
        "check": "apt",
        "update": "apt update -y && apt upgrade -y",
        "dry_run": "apt update -y && apt list --upgradable"  # ensure cache updated first
    },
    "dnf": {
        "check": "dnf",
        "update": "dnf -y upgrade",
        "dry_run": "dnf check-update"  # dnf check-update refreshes metadata
    },
    "yum": {
        "check": "yum",
        "update": "yum -y update",
        "dry_run": "yum check-update"  # yum check-update refreshes metadata
    },
    "zypper": {
        "check": "zypper",
        "update": "zypper refresh && zypper update -y",
        "dry_run": "zypper refresh && zypper list-updates"  # refresh first
    },
    "pacman": {
        "check": "pacman",
        "update": "pacman -Syu --noconfirm",
        "dry_run": "pacman -Sy && pacman -Qu"  # refresh db first
    },
    "apk": {
        "check": "apk",
        "update": "apk update && apk upgrade",
        "dry_run": "apk update && apk version -l '<'"  # update db first
    }
}
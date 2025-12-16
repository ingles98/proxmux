"""Helpers for discovering Proxmox guests and host information.

Small helpers that call out to the Proxmox CLI (pct/qm) to collect
guest configuration, status, networking and storage details. Functions
are intentionally defensive: they log failures and return empty values
rather than raising so discovery can continue.
"""

import subprocess
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .utils import log_debug, log_warn, log_info, PACKAGE_MANAGERS


# ------------------------
# HELPERS
# ------------------------
def run(cmd: str) -> Optional[str]:
    """Run `cmd` in a shell and return trimmed stdout, or ``None`` on failure.

    Uses ``subprocess.run`` with ``capture_output`` and ``text``. The
    function logs an informational warning if the command cannot be
    executed (``OSError``) and returns ``None`` for non-zero exit codes.
    """
    log_debug(f"Running command: {cmd}")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        log_debug(f"\tCommand stdout: {r.stdout.strip()}")
        log_debug(f"\tCommand stderr: {r.stderr.strip()}")
        log_debug(f"\tCommand return code: {r.returncode}")
    except OSError as e:
        log_warn(f"Command failed: {cmd} ({e})")
        return None

    if r.returncode != 0:
        return None
    return r.stdout.strip()


def parse_ip_json() -> List[Dict[str, Any]]:
    """Return parsed output from ``ip -j addr`` excluding the loopback.

    Returns an empty list if the command fails or the JSON cannot be
    decoded.
    """
    out = run("ip -j addr")
    if not out:
        return []
    try:
        data = json.loads(out)
        return [i for i in data if i.get("ifname") != "lo"]
    except json.JSONDecodeError as e:
        log_warn(f"Failed to parse host IP JSON: {e}")
        return []


def parse_pct_config(ctid: str) -> Dict[str, Any]:
    """Parse the output of ``pct config <ctid>`` into a mapping."""
    cfg: Dict[str, Any] = {}
    out = run(f"pct config {ctid}")
    if out:
        for line in out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def parse_qm_config(vmid: str) -> Dict[str, Any]:
    """Parse the output of ``qm config <vmid>`` into a mapping."""
    cfg: Dict[str, Any] = {}
    out = run(f"qm config {vmid}")
    if out:
        for line in out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def get_lxc_status(ctid: str) -> str:
    """Return ``'running'`` if the LXC container is running, else ``'offline'``."""
    s = run(f"pct status {ctid}")
    return "running" if s and "running" in s.lower() else "offline"


def get_vm_status(vmid: str) -> str:
    """Return ``'running'`` if the VM is running, else ``'offline'``."""
    s = run(f"qm status {vmid}")
    return "running" if s and "running" in s.lower() else "offline"


def get_vm_ips(vmid: str) -> List[str]:
    """Return a list of IPv4 addresses for the given VM via guest exec.

    Returns an empty list if the guest agent is unavailable or the
    returned JSON cannot be parsed.
    """
    if run(f"qm guest exec {vmid} -- echo ok") is None:
        return []
    out = run(f"qm guest exec {vmid} -- ip -j addr")
    if not out:
        return []
    try:
        data = json.loads(json.loads(out)["out-data"])
        ips: List[str] = []
        for iface in data:
            log_debug(f"\tVM {vmid} iface: {iface}")
            if iface.get("ifname") == "lo":
                continue
            for a in iface.get("addr_info", []):
                if a.get("family") == "inet":
                    ips.append(a["local"])
        return ips
    except (json.JSONDecodeError, TypeError):
        return []


def guest_exec(guest_id: str, cmd: str, lxc: bool = True) -> Optional[str]:
    """Execute `cmd` inside a guest (LXC or VM) and return stdout or None."""
    if lxc:
        return run(f"pct exec {guest_id} -- bash -c '{cmd}'")
    return run(f"qm guest exec {guest_id} -- bash -c '{cmd}'")


def detect_package_manager(guest_id: str, lxc: bool = True) -> Dict[str, Optional[str]]:
    """Detect a guest's package manager and return update commands.

    Returns a mapping with keys ``name``, ``update_command`` and
    ``dry_run_command``.
    """
    for pm, info in PACKAGE_MANAGERS.items():
        if guest_exec(guest_id, f"command -v {info['check']}", lxc):
            return {
                "name": pm,
                "update_command": info["update"],
                "dry_run_command": info["dry_run"],
            }
    return {"name": "unknown", "update_command": None, "dry_run_command": None}


def detect_pve_updateable(guest_id: str, lxc: bool = True) -> Dict[str, Any]:
    """Detect if the guest exposes a top-level `update` script.

    Only meaningful for LXC guests; returns ``updateable`` boolean and
    the associated ``update_command`` (or ``None``).
    """
    if not lxc:
        return {"updateable": False, "update_command": None}
    update_path = guest_exec(guest_id, "command -v update", lxc)
    if update_path:
        cmd_content = guest_exec(guest_id, f"cat {update_path}", lxc)
        return {"updateable": True, "update_command": cmd_content or "update"}
    return {"updateable": False, "update_command": None}


# ------------------------
# DEVICE, NETWORK, STORAGE EXTRACTION
# ------------------------
def extract_host_devices(cfg: Dict[str, Any]) -> None:
    """Collect all keys starting with 'dev' into cfg['host_devices'] and remove them.

    Scans the provided cfg mapping for keys beginning with 'dev', gathers their
    values into a list under the 'host_devices' key, and deletes the original
    'dev*' keys from the mapping (mutation happens in-place).
    """
    devices = [cfg[k] for k in list(cfg.keys()) if k.startswith("dev")]
    for k in list(cfg.keys()):
        if k.startswith("dev"):
            del cfg[k]
    if devices:
        cfg["host_devices"] = devices


def extract_network(cfg: Dict[str, Any]) -> None:
    """Extract network entries from cfg into a 'network' list and remove originals.

    Scans cfg for keys matching 'net\\d+' and collects each value into a list of
    dicts with keys 'raw' and 'name', and extracts an 'ip' field when an 'ip=...'
    pattern is present; modifies cfg in-place by deleting the original net* keys
    and setting cfg['network'] when entries are found.
    """
    networks: List[Dict[str, Any]] = []
    for k in list(cfg.keys()):
        if re.match(r"net\d+", k):
            net_raw = cfg[k]
            net_entry = {"raw": net_raw, "name": k}
            m = re.search(r"ip=([^,]+)", net_raw)
            if m:
                net_entry["ip"] = m.group(1)
            networks.append(net_entry)
            del cfg[k]
    if networks:
        cfg["network"] = networks


def extract_storage(cfg: Dict[str, Any], lxc: bool = True) -> None:
    """Extract storage-related configuration into cfg['storage'] and remove the original keys.

    For LXC containers this collects 'rootfs' and 'swap'; for VMs this collects
    disk device entries matching scsi/ide/sata and the 'scsihw' setting. The
    function mutates the provided cfg mapping in-place.
    """
    storage: List[Dict[str, Any]] = []
    if lxc:
        for key in ["rootfs", "swap"]:
            if key in cfg:
                storage.append({"type": key, "value": cfg[key]})
                del cfg[key]
    else:
        for key in list(cfg.keys()):
            if re.match(r"(scsi|ide|sata)\d+", key):
                val_clean = re.sub(r"vm-\d+-disk-\d+", "", cfg[key])
                storage.append({"type": key, "value": val_clean})
                del cfg[key]
        if "scsihw" in cfg:
            storage.append({"type": "scsihw", "value": cfg["scsihw"]})
            del cfg["scsihw"]
    if storage:
        cfg["storage"] = storage


# ------------------------
# GUEST DISCOVERY
# ------------------------
def _parse_os_release(content: Optional[str]) -> Dict[str, str]:
    res: Dict[str, str] = {}
    if not content:
        return res
    for line in content.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.lower()
        if k in {"name", "pretty_name", "id", "version_id", "version_codename"}:
            res[k] = v.strip().strip('"').strip("'")
    return res


def _get_enabled_services(guest_id: str, lxc: bool) -> List[str]:
    svc = guest_exec(
        guest_id, "systemctl list-unit-files --type=service --state=enabled", lxc
    )
    if not svc:
        return []
    return [
        line.split()[0]
        for line in svc.splitlines()
        if line.strip() and not line.startswith("UNIT FILE")
    ]


def _get_docker_info(guest_id: str, lxc: bool) -> Dict[str, Any]:
    docker = {"enabled": False, "containers": [], "compose_files": []}
    if guest_exec(guest_id, "command -v docker >/dev/null && echo yes", lxc) != "yes":
        return docker
    docker["enabled"] = True
    inspect = guest_exec(guest_id, "docker inspect $(docker ps -q)", lxc)
    try:
        docker["containers"] = json.loads(inspect) if inspect else []
    except json.JSONDecodeError:
        docker["containers"] = []
    compose = guest_exec(
        guest_id, "find / -type f -name '*-compose.yml' 2>/dev/null", lxc
    )
    docker["compose_files"] = compose.splitlines() if compose else []
    return docker


def _compose_update_command(base: Optional[str], docker: Dict[str, Any]) -> str:
    update_cmd = base or ""
    if not docker.get("enabled"):
        return update_cmd
    docker_update_cmds = ["docker system prune -f"]
    if docker.get("containers"):
        docker_update_cmds.append("docker pull $(docker images -q)")
    if docker.get("compose_files"):
        docker_update_cmds.append(
            f"docker-compose -f {' '.join(docker['compose_files'])} pull"
        )
    docker_update = " && ".join(docker_update_cmds)
    if not docker_update:
        return update_cmd
    return f"{update_cmd} && {docker_update}" if update_cmd else docker_update


def discover_guest(
    guest_id: str, lxc: bool = True, existing_hostname: Optional[str] = None
) -> Dict[str, Any]:
    """Collect discovery information for a single guest.

    Returns a dictionary of discovered properties such as hostname,
    services, docker info and package manager data. Failures are
    logged and missing data is represented by empty structures.
    """
    log_info(f"Discovering guest: {'LXC' if lxc else 'VM'} {guest_id}")
    info: Dict[str, Any] = {"type": "lxc" if lxc else "vm"}
    info["hostname"] = guest_exec(guest_id, "hostname", lxc) or existing_hostname or "unknown"

    os_release = guest_exec(guest_id, "cat /etc/os-release", lxc)
    info["os"] = _parse_os_release(os_release)

    info["services_enabled"] = _get_enabled_services(guest_id, lxc)

    docker = _get_docker_info(guest_id, lxc)
    info["docker"] = docker

    pkg = detect_package_manager(guest_id, lxc)
    pve_update = detect_pve_updateable(guest_id, lxc)
    update_cmd = _compose_update_command(pkg.get("update"), docker) if False else _compose_update_command(pkg.get("update_command", "") if isinstance(pkg, dict) else pkg.get("update_command", ""), docker)  # keep compatibility with pkg dict key name
    # Normalise update_command retrieval (pkg uses "update_command" in existing code)
    if not update_cmd:
        update_cmd = _compose_update_command(pkg.get("update_command", "") if isinstance(pkg, dict) else "", docker)

    info["package_manager"] = {
        "manager": pkg.get("name"),
        "update_command": update_cmd,
        "update_dry_run_command": pkg.get("dry_run_command"),
        "pve_updateable": pve_update.get("updateable"),
        "pve_update_command": pve_update.get("update_command"),
    }

    cfgs = guest_exec(
        guest_id, "find /etc -type f -name '*.conf' 2>/dev/null | head -n 50", lxc
    )
    info["app_config_files"] = cfgs.splitlines() if cfgs else []

    return info


def discover_stack(out_file: str) -> Dict[str, Any]:
    """Discover the local Proxmox environment and write YAML to `out_file`.

    Returns the discovered dictionary structure.
    """
    log_info("Starting Proxmox environment discovery")
    stack: Dict[str, Any] = {
        "proxmox": {
            "hostname": run("hostname"),
            "networks": parse_ip_json(),
            "guests": [],
        }
    }

    for ctid in (run("pct list | awk 'NR>1 {print $1}'") or "").splitlines():
        cfg = parse_pct_config(ctid)
        cfg.update(
            {"id": ctid, "ctid": ctid, "type": "lxc", "status": get_lxc_status(ctid)}
        )
        extract_host_devices(cfg)
        extract_network(cfg)
        extract_storage(cfg, lxc=True)
        stack["proxmox"]["guests"].append(cfg)

    for vmid in (run("qm list | awk 'NR>1 {print $1}'") or "").splitlines():
        cfg = parse_qm_config(vmid)
        cfg.update(
            {
                "id": vmid,
                "vmid": vmid,
                "type": "vm",
                "status": get_vm_status(vmid),
                "ips": get_vm_ips(vmid),
            }
        )
        extract_host_devices(cfg)
        extract_network(cfg)
        extract_storage(cfg, lxc=False)
        stack["proxmox"]["guests"].append(cfg)

    for guest in stack["proxmox"]["guests"]:
        if guest["status"] != "running":
            log_warn(f"{guest['type']} {guest['id']} offline, skipping guest discovery")
            continue
        guest.update(
            discover_guest(
                guest["id"],
                lxc=(guest["type"] == "lxc"),
                existing_hostname=guest.get("hostname") or guest.get("name"),
            )
        )

    Path(out_file).write_text(yaml.safe_dump(stack, sort_keys=False), encoding="utf-8")
    log_info(f"Saved YAML to {out_file}")
    return stack

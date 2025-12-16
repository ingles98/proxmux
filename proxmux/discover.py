import subprocess
import json
import yaml
import re
from .utils import log_warn, log_info, PACKAGE_MANAGERS


# ------------------------
# HELPERS
# ------------------------
def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            return None
        return r.stdout.strip()
    except Exception as e:
        log_warn(f"Command failed: {cmd} ({e})")
        return None

def parse_ip_json():
    out = run("ip -j addr")
    if not out:
        return []
    try:
        data = json.loads(out)
        return [i for i in data if i.get("ifname") != "lo"]
    except Exception as e:
        log_warn(f"Failed to parse host IP JSON: {e}")
        return []

def parse_pct_config(ctid):
    cfg = {}
    out = run(f"pct config {ctid}")
    if out:
        for line in out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                cfg[k.strip()] = v.strip()
    return cfg

def parse_qm_config(vmid):
    cfg = {}
    out = run(f"qm config {vmid}")
    if out:
        for line in out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                cfg[k.strip()] = v.strip()
    return cfg

def get_lxc_status(ctid):
    s = run(f"pct status {ctid}")
    return "running" if s and "running" in s.lower() else "offline"

def get_vm_status(vmid):
    s = run(f"qm status {vmid}")
    return "running" if s and "running" in s.lower() else "offline"

def get_vm_ips(vmid):
    if run(f"qm guest exec {vmid} -- echo ok") is None:
        return []
    out = run(f"qm guest exec {vmid} -- ip -j addr")
    if not out:
        return []
    try:
        data = json.loads(out)
        ips = []
        for iface in data:
            if iface.get("ifname") == "lo":
                continue
            for a in iface.get("addr_info", []):
                if a.get("family") == "inet":
                    ips.append(a["local"])
        return ips
    except Exception:
        return []

def guest_exec(id, cmd, lxc=True):
    if lxc:
        return run(f"pct exec {id} -- bash -c '{cmd}'")
    return run(f"qm guest exec {id} -- bash -c '{cmd}'")

def detect_package_manager(id, lxc=True):
    for pm, info in PACKAGE_MANAGERS.items():
        if guest_exec(id, f"command -v {info['check']}", lxc):
            return {"name": pm, "update_command": info["update"], "dry_run_command": info["dry_run"]}
    return {"name": "unknown", "update_command": None, "dry_run_command": None}

def detect_pve_updateable(id, lxc=True):
    if not lxc:
        return {"updateable": False, "update_command": None}
    update_path = guest_exec(id, "command -v update", lxc)
    if update_path:
        cmd_content = guest_exec(id, f"cat {update_path}", lxc)
        return {"updateable": True, "update_command": cmd_content or "update"}
    return {"updateable": False, "update_command": None}

# ------------------------
# DEVICE, NETWORK, STORAGE EXTRACTION
# ------------------------
def extract_host_devices(cfg):
    devices = [cfg[k] for k in list(cfg.keys()) if k.startswith("dev")]
    for k in list(cfg.keys()):
        if k.startswith("dev"):
            del cfg[k]
    if devices:
        cfg["host_devices"] = devices

def extract_network(cfg, lxc=True):
    networks = []
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

def extract_storage(cfg, lxc=True):
    storage = []
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
def discover_guest(id, lxc=True, existing_hostname=None):
    log_info(f"Discovering guest: {'LXC' if lxc else 'VM'} {id}")
    info = {"type": "lxc" if lxc else "vm"}
    hostname = guest_exec(id, "hostname", lxc)
    info["hostname"] = hostname or existing_hostname or "unknown"

    os_release = guest_exec(id, "cat /etc/os-release", lxc)
    os_info = {}
    if os_release:
        for line in os_release.splitlines():
            if "=" not in line: continue
            k, v = line.split("=", 1)
            k = k.lower()
            if k in {"name","pretty_name","id","version_id","version_codename"}:
                os_info[k] = v.strip().strip('"').strip("'")
    info["os"] = os_info

    svc = guest_exec(id, "systemctl list-unit-files --type=service --state=enabled", lxc)
    services = [line.split()[0] for line in svc.splitlines() if line.strip() and not line.startswith("UNIT FILE")] if svc else []
    info["services_enabled"] = services

    docker = {"enabled": False, "containers": [], "compose_files": []}
    if guest_exec(id, "command -v docker >/dev/null && echo yes", lxc) == "yes":
        docker["enabled"] = True
        inspect = guest_exec(id, "docker inspect $(docker ps -q)", lxc)
        docker["containers"] = json.loads(inspect) if inspect else []
        compose = guest_exec(id, "find / -type f -name '*-compose.yml' 2>/dev/null", lxc)
        docker["compose_files"] = compose.splitlines() if compose else []
    info["docker"] = docker

    pkg = detect_package_manager(id, lxc)
    pve_update = detect_pve_updateable(id, lxc)
    update_cmd = pkg.get("update_command", "")
    if docker["enabled"]:
        docker_update_cmds = ["docker system prune -f"]
        if docker["containers"]:
            docker_update_cmds.append("docker pull $(docker images -q)")
        if docker["compose_files"]:
            docker_update_cmds.append("docker-compose -f {} pull".format(" ".join(docker["compose_files"])))
        docker_update = " && ".join(docker_update_cmds)
        if docker_update:
            update_cmd = f"{update_cmd} && {docker_update}" if update_cmd else docker_update

    info["package_manager"] = {
        "manager": pkg.get("name"),
        "update_command": update_cmd,
        "update_dry_run_command": pkg.get("dry_run_command"),
        "pve_updateable": pve_update.get("updateable"),
        "pve_update_command": pve_update.get("update_command")
    }

    cfgs = guest_exec(id, "find /etc -type f -name '*.conf' 2>/dev/null | head -n 50", lxc)
    info["app_config_files"] = cfgs.splitlines() if cfgs else []

    return info

def discover_stack(out_file):
    log_info("Starting Proxmox environment discovery")
    stack = {"proxmox": {"hostname": run("hostname"), "networks": parse_ip_json(), "guests": []}}

    for ctid in (run("pct list | awk 'NR>1 {print $1}'") or "").splitlines():
        cfg = parse_pct_config(ctid)
        cfg.update({"id": ctid, "ctid": ctid, "type": "lxc", "status": get_lxc_status(ctid)})
        extract_host_devices(cfg)
        extract_network(cfg, lxc=True)
        extract_storage(cfg, lxc=True)
        stack["proxmox"]["guests"].append(cfg)

    for vmid in (run("qm list | awk 'NR>1 {print $1}'") or "").splitlines():
        cfg = parse_qm_config(vmid)
        cfg.update({"id": vmid, "vmid": vmid, "type": "vm", "status": get_vm_status(vmid), "ips": get_vm_ips(vmid)})
        extract_host_devices(cfg)
        extract_network(cfg, lxc=False)
        extract_storage(cfg, lxc=False)
        stack["proxmox"]["guests"].append(cfg)

    for guest in stack["proxmox"]["guests"]:
        if guest["status"] != "running":
            log_warn(f"{guest['type']} {guest['id']} offline, skipping guest discovery")
            continue
        guest.update(discover_guest(guest["id"], lxc=(guest["type"]=="lxc"), existing_hostname=guest.get("hostname") or guest.get("name")))

    with open(out_file, "w") as f:
        yaml.safe_dump(stack, f, sort_keys=False)
    log_info(f"Saved YAML to {out_file}")
    return stack

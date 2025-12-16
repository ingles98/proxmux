import subprocess
import json
import yaml
from pathlib import Path
from jinja2 import Template
from .utils import log_warn

# ------------------------
# HELPERS
# ------------------------
def run_guest_command(id, cmd, lxc=True):
    """
    Execute command on guest (LXC or VM) and return output and exit code.
    """
    try:
        full_cmd = f"pct exec {id} -- bash -c '{cmd}'" if lxc else f"qm guest exec {id} -- bash -c '{cmd}'"
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        return output.strip(), result.returncode
    except Exception as e:
        return None, -1

def count_updates(id, dry_run_cmd, lxc=True):
    """
    Run the dry-run command. Handles '&&' sequential execution.
    If the first or second command fails (non-zero exit or error JSON), return -1 and error.
    """
    cmds = [c.strip() for c in dry_run_cmd.split("&&", 1)]  # max two commands
    if len(cmds) == 2:
        out1, code1 = run_guest_command(id, cmds[0], lxc)
        if code1 != 0:
            return -1, [f"First command failed: {out1 or 'Unknown error'}"]
        dry_cmd = cmds[1]
    else:
        dry_cmd = cmds[0]

    out, code = run_guest_command(id, dry_cmd, lxc)
    if out is None or code != 0:
        return -1, [f"Command failed: {out or 'Unknown error'}"]

    # Try to detect error JSON from qm guest exec
    try:
        obj = json.loads(out)
        # If output is a dict with keys like 'err-data', treat as error
        if isinstance(obj, dict) and any(k in obj for k in ("err-data", "exitcode", "exited")):
            return -1, [f"Command failed: {json.dumps(obj, indent=2)}"]
    except Exception:
        # Not JSON, proceed
        pass

    # Filter out non-package lines
    lines = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("listing") or "warning:" in line.lower():
            continue
        lines.append(line)

    return len(lines), lines

def print_results(results, list_packages=False):
    for guest in results:
        name = guest['name']
        if guest['updates'] == -1:
            # print errors in red
            print(f"\033[1;31m{name}\033[0m ({guest['type']}, id={guest['id']}) → ERROR")
            for err in guest['packages']:
                print(f"   - {err}")
        else:
            status = f"{guest['updates']} updates"
            print(f"\033[1;34m{name}\033[0m ({guest['type']}, id={guest['id']}) → {status}")
            if list_packages:
                for pkg in guest['packages']:
                    print(f"   - {pkg}")
        print()

def run_update_check(stack_path,list_pkgs=False):
    data=yaml.safe_load(Path(stack_path).read_text())
    guests=data.get("proxmox",{}).get("guests",[])

    results = []

    for g in guests:
        name = g.get('name') or g.get("hostname") or str(g["id"])
        if g.get("status") != "running":
            log_warn(f"{g.get('type')} {g.get('id')} is offline, skipping")
            continue

        pm = g.get("package_manager", {})
        dry_run_cmd = pm.get("update_dry_run_command")
        if not dry_run_cmd:
            log_warn(f"No update command detected for {name} ({g['id']})")
            results.append({
                "id": g["id"],
                "name": name,
                "type": g["type"],
                "updates": -1,
                "packages": ["No package manager command available"]
            })
            continue

        updates_count, packages = count_updates(g["id"], dry_run_cmd, lxc=(g["type"]=="lxc"))

        results.append({
            "id": g["id"],
            "name": name,
            "type": g["type"],
            "updates": updates_count,
            "packages": packages
        })

    print_results(results, list_packages=list_pkgs)

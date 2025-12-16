# proxmux

**proxmux** is a Proxmox VE fleet discovery and maintenance toolkit.  
It allows you to discover, inventory, visualize, and audit updates for Proxmox VMs and LXCs directly from the Proxmox host.

---

## ⚠️ Important Warnings & Requirements

> **This toolkit is intended to run ONLY on Proxmox VE hosts.**

Before using proxmux, please read carefully:

- ✅ **Must be run on a Proxmox VE node**
- ✅ **Requires root privileges** (or equivalent permissions)
- ✅ **Relies on Proxmox CLI tools**: `pct`, `qm`, `ip`, `bash`
- ⚠️ **VM guest inspection requires QEMU Guest Agent**
- ⚠️ Some features are skipped for offline guests

Running proxmux on non-Proxmox systems is **not supported**.

---

## ✨ Features

- 🔍 Discover all Proxmox VMs and LXCs
- 📄 Generate a structured YAML inventory
- 🌐 Produce an interactive HTML visualization
- 📦 Detect package managers inside guests
- 🔎 Audit pending system updates (dry-run only)
- 🧱 Designed for future lifecycle operations (updates, reboots, maintenance)

---

## 🚀 Installation

proxmux is distributed via **PyPI** and is designed to be installed using **pipx**, ensuring a clean and isolated Python environment.

---

### 🔧 Automatic Installation (Recommended)

This method installs `pipx` if needed and then installs proxmux.

```bash
curl -fsSL https://raw.githubusercontent.com/ingles98/proxmux/main/install.sh | bash
proxmux --help
```

### 🔧 Manual Installation

#### 1️⃣ Install pipx (Debian / Proxmox VE)

```bash
apt update
apt install -y pipx
```

#### 2️⃣ Install proxmux from PyPI

```bash
pipx install proxmux
```


### Verify installation:

```bash
proxmux --help
```

## 🔄 Updating & Removal

Update to the latest version:

```bash
pipx upgrade proxmux
```

Uninstall:

```bash
pipx uninstall proxmux
```

---

## 📘 Usage

Discover Proxmox environment and generate inventory + HTML

```bash
proxmux discover -i prox_stack.yml -o stack_view.html
```

Regenerate HTML from an existing inventory

```bash
proxmux html -i prox_stack.yml -o stack_view.html
```

Check pending updates on guests

```bash
proxmux updates
```

List individual packages pending update:

```bash
proxmux updates --list
```

## 📂 Output Files

`prox_stack.yml` — structured inventory of the Proxmox environment

`stack_view.html` — interactive HTML visualization

Both files are safe to version-control or archive.

## 🧠 Notes & Limitations

Offline guests are skipped automatically

VM inspection requires QEMU Guest Agent

Updates are audit-only for now (no changes applied)

proxmux is designed to be safe by default

## 🛣️ Roadmap

- `proxmux upgrade` `--dry-run` / `--apply`

- Guest reboot orchestration

- JSON / machine-readable output modes

- Plugin hooks per guest

- CI-friendly non-interactive mode

## 📜 License

MIT License

## 🤝 Contributing

Issues, ideas, and pull requests are welcome.
proxmux aims to remain simple, safe, and transparent.
# `desktopctl`

A lightweight, UI-agnostic command-line backend for controlling common Linux
desktop functionality.

`desktopctl` provides a stable interface between replaceable frontends and Linux
system services. It does not depend on Rofi, Quickshell, Waybar, Hyprland, or any
other specific desktop configuration.

## Features

- Control WiFi through NetworkManager:
  - show status, visible networks, and saved profiles;
  - enable, disable, and scan;
  - connect, disconnect, and forget profiles.
- Control Bluetooth through BlueZ:
  - show status, known devices, and paired devices;
  - enable, disable, and scan;
  - pair, connect, disconnect, and forget devices.
- Inspect power state through UPower and control system power profiles:
  - show battery, charging, external-power, and active-profile status;
  - select `power-saver`, `balanced`, or `performance`.
- Provide stable machine-readable JSON for informational commands.
- Communicate directly with Linux services over the system D-Bus.

Detailed command documentation is available in the
[project wiki](https://github.com/kmi784/desktopctl/wiki).

## Requirements

- Python 3.13 or newer
- NetworkManager with a WiFi-capable device
- BlueZ with a Bluetooth adapter
- UPower
- A Power Profiles service compatible with `org.freedesktop.UPower.PowerProfiles`
- A running system D-Bus

The Python package depends on `dbus-python` and PyGObject. Depending on the Linux
distribution, installing these packages may require the corresponding system
libraries and development headers.

## Installation

```sh
mkdir -p ~/.local/share/desktopctl ~/.local/bin
python3 -m venv ~/.local/share/desktopctl/venv
~/.local/share/desktopctl/venv/bin/python -m pip install git+https://github.com/kmi784/desktopctl.git
ln -s ~/.local/share/desktopctl/venv/bin/desktopctl ~/.local/bin/desktopctl
```

Ensure `~/.local/bin` is included in `PATH`, then verify the installation:

```sh
desktopctl --help
```

## Usage

Inspect the available modules and commands through the built-in help:

```sh
desktopctl --help
desktopctl wifi --help
desktopctl bluetooth --help
desktopctl power --help
```

Typical examples:

```sh
desktopctl wifi status --json
desktopctl wifi scan
desktopctl wifi visible

desktopctl bluetooth status --json
desktopctl bluetooth scan
desktopctl bluetooth visible

desktopctl power status --json
desktopctl power profile balanced
```

Use the global `--debug` option before the module name to enable diagnostic
logging:

```sh
desktopctl --debug wifi status
```

## Development

Create a local virtual environment and install the project with its development
dependencies:

```sh
git clone https://github.com/kmi784/desktopctl.git
cd desktopctl
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite and static checks through the project environment:

```sh
.venv/bin/pytest
.venv/bin/ruff check src tests
```

## Exit codes

`desktopctl` uses the following general exit codes:

- `0`: success
- `1`: backend operation failed
- `2`: invalid command or arguments

Backend errors are written to standard error.

## Roadmap

- [x] WiFi control
- [x] Bluetooth control
- [x] Power status and profile control
- [ ] Audio control
- [ ] Display brightness control

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

# `desktopctl`

A lightweight command-line tool for controlling common Linux desktop functionality.

## Features

- Provide machine-readable JSON output for listing commands using the `--json` option

## Prerequisites

- Python 3.13 or newer
- NetworkManager command-line tool `nmcli`
- BlueZ
- D-Bus  

## Installation

```sh
git clone https://github.com/kmi784/desktopctl.git
cd desktopctl
mkdir -p ~/.local/share/desktopctl ~/.local/bin
python3 -m venv ~/.local/share/desktopctl/venv
~/.local/share/desktopctl/venv/bin/python -m pip install .
ln -s ~/.local/share/desktopctl/venv/bin/desktopctl ~/.local/bin/desktopctl
```

## Usage

```sh
desktopctl --help
```

For detailed usage instructions, see the [project wiki](https://github.com/kmi784/desktopctl/wiki).

## Development

```sh
git clone https://github.com/kmi784/desktopctl.git
cd desktopctl
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Tests

Run the test suite:

```sh
pytest
```

## Formatting and linting

### Linting

```sh
ruff check . # use --fix if Ruff should fix the violations
```

### Formatting

```sh
ruff format .
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Roadmap

- [x] Control WiFi functionality
- [ ] Control Bluetooth functionality
- [ ] Control audio functionality
- [ ] Control display brightness
- [ ] Control power profiles (Performance, Balanced, and Power Saver)

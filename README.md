# New Package

## Perquisites
- NetworkManager command-line tool `nmcli`
- Bluetooth command-line tool `bluetoothctl`

## Quick start

- Installation:
    ```sh
    git clone https://github.com/kmi784/desktopctl.git    
    cd desktopctl
    mkdir -p ~/.local/share/desktopctl ~/.local/bin
    python3 -m venv ~/.local/share/desktopctl/venv
    ~/.local/share/desktopctl/venv/bin/python -m pip install .
    ln -s ~/.local/share/desktopctl/venv/bin/desktopctl ~/.local/bin/desktopctl
    ```
- Development:
    ```sh
    git clone https://github.com/kmi784/desktopctl.git
    cd desktopctl
    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    ```

## Tests

For testing run:
```sh
pytest
```

## Formatting and Linting

- Linting
    ```sh
    ruff check . # use --fix if ruff should fix the violations
    ```

- Formatting
    ```sh
    ruff format .
    ```

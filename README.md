# New Package

## Perquisites
- NetworkManager command-line tool `nmcli`
- Bluetooth command-line tool `bluetoothctl`

## Quick start

- Installation:
    ```sh
    pip install git+<url>.git
    ```
- Development:
    ```sh
    git clone <url>.git
    cd New\ Package
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

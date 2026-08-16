def print_table(data: list[dict]) -> None:
    """Print dictionary records as a table."""
    if not data:
        return

    columns = list(data[0])
    rows = [
        {
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in row.items()
        }
        for row in data
    ]
    widths = {
        column: max(len(column), *(len(row[column]) for row in rows))
        for column in columns
    }

    def _print_row(row: dict[str, str]) -> None:
        print(
            "  ".join(f"{row[column]:<{widths[column]}}" for column in columns).rstrip()
        )

    _print_row({column: column.upper() for column in columns})

    for row in rows:
        _print_row(row)

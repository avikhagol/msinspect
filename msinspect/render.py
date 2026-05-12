from rich.table import Table


def render_ms_table(data):
    first_row = data["start_row"] + 1 if data["end_row"] > data["start_row"] else 0
    last_row = data["end_row"]

    table = Table(
        title=(
            f"{data['name']} rows "
            f"({first_row}-{last_row} of {data['nrows']}, "
            f"showing {data['shown_rows']})"
        ),
        show_lines=True,
    )

    table.add_column("#", style="bold cyan", no_wrap=True)

    for column in data["columns"]:
        table.add_column(column, overflow="fold")

    row_indices = data.get("row_indices") or range(
        data["start_row"],
        data["start_row"] + data["shown_rows"],
    )

    for row_index, row in zip(row_indices, data["rows"]):
        table.add_row(
            str(row_index),
            *(str(row.get(column, "")) for column in data["columns"]),
        )

    return table


def render_summary(summary):
    table = Table(title="Measurement Set Summary")

    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="default")

    for key, value in summary.items():
        if isinstance(value, list):
            value = ", ".join(map(str, value))

        table.add_row(str(key), str(value))

    return table


def render_main_summary(summary):
    table = Table(title="Observation Summary")

    table.add_column("Metric", style="bold cyan")
    table.add_column("Value")

    keys = [
        "nrows",
        "nantennas",
        "nfields",
        "nspw",
        "nscans",
    ]

    for k in keys:
        if k in summary:
            table.add_row(k, str(summary[k]))
    return table

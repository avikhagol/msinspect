
from rich.table import Table

def render_summary(summary):
    table = Table(title="Measurement Set Summary")

    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

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

# tui.py

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Select, Static
from casacore.tables import table
from rich.table import Table

from msinspect.read import ms_summary
from msinspect.render import render_summary

class MSApp(App):
    def __init__(self, vis):
        super().__init__()
        self.vis = vis

    def compose(self) -> ComposeResult:
        with table(self.vis, ack=False) as t:
            self.subtables = sorted([
                k for k, v in t.getkeywords().items()
                if isinstance(v, str) and "Table:" in v
            ])

        yield Header()
        yield Select(
            [(s, s) for s in self.subtables],
            prompt="Select subtable",
            id="subtables",
        )
        yield Static(render_summary(ms_summary(self.vis)), id="info")
        yield Footer()

    def on_select_changed(self, event):
        summary = ms_summary(f"{self.vis}/{event.value}")
        self.query_one("#info", Static).update(
            render_summary(summary)
        )
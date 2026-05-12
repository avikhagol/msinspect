# tui.py

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Header, Footer, Select, Static
from casacore.tables import table

from msinspect.read import ms_summary, read_ms_table
from msinspect.render import render_ms_table, render_summary


class MSApp(App):
    CSS = """
    #pager {
        height: auto;
    }

    #pager Button {
        width: auto;
        margin-right: 1;
    }

    #table-view {
        height: 1fr;
    }
    """

    def __init__(self, vis, *, read=False, read_rows=20, table_name="MAIN"):
        super().__init__()
        self.vis = vis
        self.read = read
        self.read_rows = read_rows
        self.selected_table = table_name
        self.start_row = 0

    def _table_path(self, name):
        if name == "MAIN":
            return self.vis

        return f"{self.vis}/{name}"

    def _render_selected_table(self, name):
        table_path = self._table_path(name)

        if self.read:
            return render_ms_table(
                read_ms_table(
                    table_path,
                    max_rows=self.read_rows,
                    start_row=self.start_row,
                )
            )

        return render_summary(ms_summary(table_path))

    def _selected_nrows(self):
        with table(self._table_path(self.selected_table), readonly=True, ack=False) as t:
            return t.nrows()

    def _update_info(self):
        self.query_one("#info", Static).update(
            self._render_selected_table(self.selected_table)
        )

    def compose(self) -> ComposeResult:
        with table(self.vis, ack=False) as t:
            self.subtables = sorted([
                k for k, v in t.getkeywords().items()
                if isinstance(v, str) and "Table:" in v
            ])

        yield Header()
        table_names = ["MAIN", *self.subtables]
        if self.selected_table not in table_names:
            self.selected_table = "MAIN"

        yield Select(
            [(s, s) for s in table_names],
            value=self.selected_table,
            prompt="Select table",
            id="subtables",
        )
        if self.read:
            with Horizontal(id="pager"):
                yield Button(f"< Prev {self.read_rows}", id="prev-page")
                yield Button(f"Next {self.read_rows} >", id="next-page")
        with VerticalScroll(id="table-view"):
            yield Static(self._render_selected_table(self.selected_table), id="info")
        yield Footer()

    def on_select_changed(self, event):
        if event.value == Select.BLANK:
            return

        self.selected_table = event.value
        self.start_row = 0
        self._update_info()

    def on_button_pressed(self, event):
        if not self.read:
            return

        if event.button.id == "next-page":
            nrows = self._selected_nrows()
            last_start = max(0, ((nrows - 1) // self.read_rows) * self.read_rows)
            self.start_row = min(self.start_row + self.read_rows, last_start)
        elif event.button.id == "prev-page":
            self.start_row = max(0, self.start_row - self.read_rows)
        else:
            return

        self._update_info()

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console

from msinspect.read import ms_summary, read_ms_table
from msinspect.render import render_main_summary, render_ms_table, render_summary


PLOT_MODES = ("plot", "vplot", "radplot", "projplot", "uvplot", "wtplot")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")

    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")

    return parsed


def _render_summary(
    vis: str,
    *,
    mini: bool,
    save_html: bool,
    tui: bool,
    read_table: str | None,
    read_rows: int,
    start_row: int = 0,
) -> int:
    if tui:
        from msinspect.tui import MSApp

        MSApp(
            vis,
            read=read_table is not None,
            read_rows=read_rows,
            table_name=read_table or "MAIN",
            start_row=start_row,
        ).run()
        return 0

    console = Console(record=True)
    if read_table is not None:
        table_path = vis if read_table == "MAIN" else str(Path(vis) / read_table)
        console.print(
            render_ms_table(
                read_ms_table(
                    table_path,
                    max_rows=read_rows,
                    start_row=start_row,
                )
            )
        )
    else:
        summary = ms_summary(vis)
        renderer = render_main_summary if mini else render_summary
        console.print(renderer(summary))

    if save_html:
        htmlfile = Path(vis).name + ".html"
        console.save_html(htmlfile)
        console.print(f"[bold green]Saved HTML report to {htmlfile} [/bold green]")

    return 0


def _run_plot(plot_args: list[str]) -> int:
    from msinspect import plot as plot_cli

    old_argv = sys.argv
    sys.argv = [old_argv[0] + " plot", *plot_args]
    try:
        return plot_cli.main()
    finally:
        sys.argv = old_argv


def _summary_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Render a Measurement Set summary.",
    )
    parser.add_argument("vis", help="Measurement Set path")
    parser.add_argument("--mini", action="store_true", help="Render compact summary.")
    parser.add_argument("--save-html", action="store_true", help="Save summary as HTML.")
    parser.add_argument("--tui", action="store_true", help="Open the Textual TUI.")
    parser.add_argument(
        "--read",
        nargs="?",
        const="MAIN",
        metavar="TABLE",
        help="Render table rows, optionally from a subtable such as ANTENNA.",
    )
    parser.add_argument(
        "--read-rows",
        type=_positive_int,
        default=20,
        help="Maximum rows to render with --read.",
    )
    parser.add_argument(
        "--start-row",
        type=_non_negative_int,
        default=0,
        help="Zero-based first row to render with --read.",
    )
    return parser


def _legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="msinspect",
        description="Inspect Measurement Sets and generate jiveplot plots.",
        epilog=(
            "Commands:\n"
            "  msinspect summary <MS_PATH> [--mini] [--save-html] [--tui] [--read [TABLE]]\n"
            "  msinspect plot <MS_PATH> "
            f"{{{','.join(PLOT_MODES)}}} [output] [plot options]\n\n"
            "Shorthand plotting is also supported:\n"
            "  msinspect <MS_PATH> "
            f"{{{','.join(PLOT_MODES)}}} [output] [plot options]"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("vis", nargs="?", help="Measurement Set path")
    parser.add_argument("--mini", action="store_true", help="Render compact summary.")
    parser.add_argument("--save-html", action="store_true", help="Save summary as HTML.")
    parser.add_argument("--tui", action="store_true", help="Open the Textual TUI.")
    parser.add_argument(
        "--read",
        nargs="?",
        const="MAIN",
        metavar="TABLE",
        help="Render table rows, optionally from a subtable such as ANTENNA.",
    )
    parser.add_argument(
        "--read-rows",
        type=_positive_int,
        default=20,
        help="Maximum rows to render with --read.",
    )
    parser.add_argument(
        "--start-row",
        type=_non_negative_int,
        default=0,
        help="Zero-based first row to render with --read.",
    )

    return parser


def cli(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "plot":
        if len(argv) == 1:
            return _run_plot(["--help"])
        return _run_plot(argv[1:])

    if argv and argv[0] == "summary":
        args = _summary_parser("msinspect summary").parse_args(argv[1:])
        return _render_summary(
            args.vis,
            mini=args.mini,
            save_html=args.save_html,
            tui=args.tui,
            read_table=args.read,
            read_rows=args.read_rows,
            start_row=args.start_row,
        )

    if len(argv) >= 2 and argv[1] in PLOT_MODES:
        return _run_plot([argv[0], argv[1], *argv[2:]])

    parser = _legacy_parser()
    args = parser.parse_args(argv)

    if not args.vis:
        parser.print_help()
        return 1

    return _render_summary(
        args.vis,
        mini=args.mini,
        save_html=args.save_html,
        tui=args.tui,
        read_table=args.read,
        read_rows=args.read_rows,
        start_row=args.start_row,
    )


if __name__ == "__main__":
    raise SystemExit(cli())

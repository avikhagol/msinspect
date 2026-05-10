import sys
from pathlib import Path
from msinspect.render import render_summary, render_main_summary

from rich.console import Console
from msinspect.read import ms_summary

def cli():
    args = sys.argv
    console = Console(record=True)
    mini = False
    save_html = False

    if len(args) < 2:
        console.print("[bold red]Usage:[/bold red] msinspect <MS_PATH>")
        sys.exit(1)

    vis = args[1]
    visp = Path(vis)

    if "--mini" in args:
        mini = True
    if "--save-html" in args:
        save_html = True
    if "--tui" in args:
        from msinspect.tui import MSApp
        MSApp(vis).run()
        return
    if not mini:
        summary = ms_summary(vis)
        console.print(render_summary(summary))
    else:
        summary = ms_summary(vis)
        console.print(render_main_summary(summary))
    if save_html:
        htmlfile = visp.name + ".html"
        console.save_html(htmlfile)
        console.print(f"[bold green]Saved HTML report to {htmlfile} [/bold green]")

if __name__ == "__main__":
    cli()
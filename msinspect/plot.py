#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pexpect
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

_theme = Theme({
    "cmd.key":    "bold cyan",
    "cmd.val":    "white",
    "status.ok":  "bold green",
    "status.err": "bold red",
    "hint":       "dim italic",
})
console = Console(stderr=True, theme=_theme)

_RASTER_FORMATS = {".png", ".jpg", ".jpeg", ".tiff", ".tif"}
_VECTOR_FORMATS = {".pdf", ".eps"}

_DEFAULT_COMMANDS = ["ckey sb[0,2,4,6,8]=8 sb[1,3,5,7,9]=3"]
_THEME_COMMANDS: dict[str, list[str]] = {
    "classic":     [],
    "modern":      ["draw both", "linew 1", "ptsz 4"],
    "publication": ["draw lines", "linew 1", "ptsz 2"],
    "dark":        ["draw both", "linew 2", "ptsz 1.5"],
}


# ── plot-type resolution ───────────────────────────────────────────────────────

def plot_type_from_xy(x: str, y: str) -> str:
    table = {
        ("amp", "chan"): "ampchan",   ("amp", "channel"): "ampchan",
        ("amp", "freq"): "ampfreq",   ("amp", "time"):    "amptime",
        ("amp", "uv"):   "ampuv",     ("amp", "uvdist"):  "ampuv",

        ("phase", "chan"):    "phachan", ("phase", "channel"): "phachan",
        ("phase", "freq"):   "phafreq", ("phase", "time"):    "phatime",
        ("phase", "uv"):     "phauv",   ("phase", "uvdist"):  "phauv",
        ("pha",   "time"):   "phatime", ("ph",    "time"):    "phatime",

        ("real",  "chan"): "rechan",  ("real",     "time"): "retime",
        ("re",    "chan"): "rechan",  ("re",       "time"): "retime",
        ("imag",  "chan"): "imchan",  ("imag",     "time"): "imtime",
        ("im",    "chan"): "imchan",  ("im",       "time"): "imtime",

        ("realimag", "chan"): "rnichan", ("realimag", "time"): "rnitime",
        ("ri",       "chan"): "rnichan", ("ri",       "time"): "rnitime",

        ("ampphase", "chan"):  "anpchan",
        ("ampphase", "freq"): "anpfreq",
        ("ampphase", "time"): "anptime",

        ("wt",     "time"): "wt",
        ("weight", "time"): "wt",
        ("uv",     ""):     "uv",
    }
    key = (x.lower(), y.lower())
    if key not in table:
        raise ValueError(f"Unsupported plot type: x={x!r}, y={y!r}")
    return table[key]


def _resolve_plot_type(args) -> str:
    if args.mode == "vplot":    return "anptime"
    if args.mode == "radplot":  return "ampuv"
    if args.mode == "projplot": return "anpuv"
    if args.mode == "uvplot":   return "uv"
    if args.mode == "wtplot":   return "wt"
    return plot_type_from_xy(args.x, args.y)


# ── Ghostscript helpers ────────────────────────────────────────────────────────

def _gs_ps_to_pdf(ps_path: str, pdf_path: str) -> bool:
    result = subprocess.run(
        [
            "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
            "-sDEVICE=pdfwrite",
            "-dEmbedAllFonts=true", "-dSubsetFonts=true",
            "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/prepress",
            f"-sOutputFile={pdf_path}", ps_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        console.print(f"[status.err]gs PS→PDF failed:[/status.err] {result.stderr.strip()}")
    return result.returncode == 0


def _pdf_to_raster(pdf_path: str, final: str, dpi: int) -> bool:
    ext  = Path(final).suffix.lower()
    stem = str(Path(final).with_suffix(""))

    if shutil.which("pdftocairo"):
        fmt = {".png": "-png", ".jpg": "-jpeg", ".jpeg": "-jpeg",
               ".tiff": "-tiff", ".tif": "-tiff"}.get(ext)
        if fmt:
            r = subprocess.run(
                ["pdftocairo", fmt, "-r", str(dpi), "-singlefile", pdf_path, stem],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                return True
            console.print(f"[hint]pdftocairo failed, falling back to gs: {r.stderr.strip()}[/hint]")

    device = {".png": "png16m", ".jpg": "jpeg", ".jpeg": "jpeg",
              ".tiff": "tiff24nc", ".tif": "tiff24nc"}.get(ext, "png16m")
    r = subprocess.run(
        [
            "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
            f"-sDEVICE={device}", f"-r{dpi}",
            "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
            f"-sOutputFile={final}", pdf_path,
        ],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        console.print(f"[status.err]gs PDF→raster failed:[/status.err] {r.stderr.strip()}")
    return r.returncode == 0


def _convert_output(ps_path: str, final: str, dpi: int) -> bool:
    """Convert PS → final format.  Does NOT delete ps_path (caller owns it)."""
    if shutil.which("gs") is None:
        console.print(
            "[status.err]ERROR:[/status.err] ghostscript (gs) not found — "
            f"cannot convert [bold]{ps_path}[/bold]"
        )
        return False

    ext = Path(final).suffix.lower()
    ok  = False

    if ext == ".pdf":
        ok = _gs_ps_to_pdf(ps_path, final)

    elif ext in _RASTER_FORMATS:
        fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            if _gs_ps_to_pdf(ps_path, tmp_pdf):
                ok = _pdf_to_raster(tmp_pdf, final, dpi)
        finally:
            Path(tmp_pdf).unlink(missing_ok=True)

    else:
        console.print(f"[status.err]ERROR:[/status.err] unsupported output format: {ext}")

    if ok:
        renderer = "pdftocairo" if (ext in _RASTER_FORMATS and shutil.which("pdftocairo")) else "gs"
        console.print(f"[status.ok]Saved:[/status.ok] [bold]{final}[/bold]  [hint]({renderer})[/hint]")

    return ok


# ── dark-theme post-processing ─────────────────────────────────────────────────

def _apply_dark(path: str) -> None:
    """Invert all colours for a dark-background look."""
    ext = Path(path).suffix.lower()

    if ext == ".pdf":
        fd, tmp = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            # Ghostscript setcolortransfer inverts R, G, B, and gray channels.
            r = subprocess.run(
                [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=pdfwrite",
                    "-c", "{1 exch sub} dup dup dup setcolortransfer",
                    "-f", path, f"-sOutputFile={tmp}",
                ],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                shutil.move(tmp, path)
            else:
                console.print(f"[hint]Dark inversion skipped: {r.stderr.strip()}[/hint]")
        finally:
            Path(tmp).unlink(missing_ok=True)

    elif ext in _RASTER_FORMATS:
        try:
            from PIL import Image, ImageOps
            ImageOps.invert(Image.open(path).convert("RGB")).save(path)
        except ImportError:
            console.print("[hint]Install Pillow for dark raster output: uv add pillow[/hint]")


# ── PDF metadata ───────────────────────────────────────────────────────────────

def _add_pdf_metadata(pdf_path: str, vis: str, plot_type: str, field: str) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return  # optional; silently skip if pypdf not installed

    parts = [Path(vis).name]
    if field:
        parts.append(field)
    parts.append(plot_type)

    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({
        "/Title":    " / ".join(parts),
        "/Subject":  f"Radio interferometry visibility plot ({plot_type})",
        "/Creator":  "msinspect",
        "/Producer": "jiveplot + Ghostscript",
    })
    with open(pdf_path, "wb") as f:
        writer.write(f)


# ── native anpuv shim (amp+phase vs UV) ───────────────────────────────────────

_JIVEPLOT_SITECUSTOMIZE = r'''
"""Runtime jiveplot patches used by msinspect."""

import os

def _install_msinspect_anpuv():
    try:
        from jiveplot import plotiterator, plots
        import numpy
    except Exception:
        return

    if "anpuv" not in plots.Plotters:
        plotter = plots.Quant2ChanPlotter(
            [plots.YTypes.amplitude, plots.YTypes.phase],
            yscaling=[plots.Scaling.auto_global, [-185, 185]],
            yheights=[0.58, 0.38],
            xtype="UV distance (lambda)",
        )
        plotter.defaultLayout = plots.layout(1, 1)
        plotter.reset()
        plots.Plotters["anpuv"] = plotter
        plots.Types = plots.enumerations.Enum(*plots.Plotters.keys())

    if "anpuv" not in plotiterator.Iterators:
        plotiterator.Iterators["anpuv"] = plotiterator.data_quantity_uvdist([
            (plots.YTypes.amplitude, numpy.ma.abs),
            (plots.YTypes.phase, lambda x: numpy.ma.angle(x, True)),
        ])

_install_msinspect_anpuv()


def _install_msinspect_dark_flags():
    if os.environ.get("MSINSPECT_DARK_FLAGS") != "1":
        return

    try:
        from jiveplot import plots
    except Exception:
        return

    if getattr(plots.Plotter.drawPoints, "_msinspect_dark_flags", False):
        return

    original_draw_points = plots.Plotter.drawPoints

    def draw_points_with_dark_flags(self, dev, x, y, tp):
        dark_symbols = {
            self.symbol[plots.SYMBOL.Flagged],
            self.symbol[plots.SYMBOL.Markedflagged],
        }
        if tp in dark_symbols:
            dev.pgsave()
            try:
                dev.pgsci(1)
                return original_draw_points(self, dev, x, y, tp)
            finally:
                dev.pgunsa()
        return original_draw_points(self, dev, x, y, tp)

    draw_points_with_dark_flags._msinspect_dark_flags = True
    plots.Plotter.drawPoints = draw_points_with_dark_flags

_install_msinspect_dark_flags()
'''


def _with_jiveplot_sitecustomize(
    env: dict[str, str], directory: str, *, dark_flags: bool = False
) -> dict[str, str]:
    """Return env that makes jplotter see msinspect's runtime patches."""
    patch = Path(directory) / "sitecustomize.py"
    patch.write_text(_JIVEPLOT_SITECUSTOMIZE, encoding="utf-8")

    patched_env = env.copy()
    pythonpath = patched_env.get("PYTHONPATH")
    patched_env["PYTHONPATH"] = (
        directory if not pythonpath else directory + os.pathsep + pythonpath
    )
    if dark_flags:
        patched_env["MSINSPECT_DARK_FLAGS"] = "1"
    return patched_env


def _run_projplot_anpuv(args) -> int:
    """Amp+phase vs UV: inject anpuv into jiveplot and run once."""
    fd, tmp_ps = tempfile.mkstemp(suffix=".ps")
    os.close(fd)
    ps_consumed = False
    rc = 0

    try:
        commands = build_commands(args, tmp_ps)
        if args.dry_run:
            return run_jplotter(
                commands, args.jplotter, args.timeout, args.dry_run, args.gui
            )

        with tempfile.TemporaryDirectory(prefix="msinspect-anpuv-") as patch_dir:
            env = _with_jiveplot_sitecustomize(
                os.environ, patch_dir, dark_flags=args.show_flags
            )
            rc = run_jplotter(
                commands, args.jplotter, args.timeout, args.dry_run, args.gui,
                env=env,
            )
            if rc != 0:
                return rc

        if args.output:
            output_ext = Path(args.output).suffix.lower()

            if output_ext == ".ps":
                shutil.move(tmp_ps, args.output)
                ps_consumed = True
                console.print(f"[status.ok]Saved:[/status.ok] [bold]{args.output}[/bold]")

            else:
                ok = _convert_output(tmp_ps, args.output, args.dpi)
                if ok and args.theme == "dark":
                    _apply_dark(args.output)
                if ok and output_ext == ".pdf":
                    _add_pdf_metadata(args.output, args.vis, "anpuv", args.field)

        if args.preview:
            output_ext = Path(args.output).suffix.lower() if args.output else ""
            if output_ext == ".png":
                _terminal_preview(args.output)
            else:
                ps_src = args.output if ps_consumed else tmp_ps
                fd2, prev_png = tempfile.mkstemp(suffix=".png")
                os.close(fd2)
                try:
                    if _convert_output(ps_src, prev_png, min(args.dpi, 150)):
                        _terminal_preview(prev_png)
                finally:
                    Path(prev_png).unlink(missing_ok=True)
    finally:
        if not ps_consumed:
            Path(tmp_ps).unlink(missing_ok=True)

    return rc


# ── terminal preview ───────────────────────────────────────────────────────────

def _terminal_preview(png_path: str) -> None:
    for tool, cmd in [
        ("chafa", ["chafa", "--colors", "full", "--size", "80x40", png_path]),
        ("viu",   ["viu",   "-w", "80",           png_path]),
        ("timg",  ["timg",  "-g", "80x40",         png_path]),
    ]:
        if shutil.which(tool):
            subprocess.run(cmd)
            return
    console.print(
        f"[hint]No terminal image viewer found (tried chafa, viu, timg). "
        f"PNG at [bold]{png_path}[/bold][/hint]"
    )


# ── command builder ────────────────────────────────────────────────────────────

def build_commands(args, tmp_ps: str) -> list[str]:
    commands = [f"ms {args.vis}"]

    if args.field:
        commands.append(f"src {args.field}")

    for item in args.select:
        commands.extend(c.strip() for c in item.split(";") if c.strip())

    commands.append(f"pt {_resolve_plot_type(args)}")

    if args.mode == "projplot":
        commands.append("new all false")
        if args.iterate == "baseline":
            commands.append("new bl true")
        elif args.iterate in {"field", "source"}:
            commands.append("new src true")
    elif args.mode == "vplot" and args.iterate in {"field", "source"}:
        commands.append("new src true")
    elif args.iterate == "baseline":
        commands.append("iter bl")
    elif args.iterate == "antenna":
        commands.append("iter ant")
    elif args.iterate in {"field", "source"}:
        commands.append("iter src")

    if args.nxy:
        nx, ny = args.nxy.lower().split("x")
        commands.append(f"nxy {nx} {ny} fixed rows")
    elif args.count:
        commands.append(f"nxy 1 {args.count} fixed rows")

    # Theme defaults first; explicit flags below can override any of them.
    for cmd in _THEME_COMMANDS.get(args.theme, []):
        commands.append(cmd)
    for cmd in _DEFAULT_COMMANDS:
        commands.append(cmd)

    if args.show_flags:
        commands.append("show both")
        commands.append("symbol Flagged=5")
        if args.draw is None:
            commands.append("draw points")

    if args.draw:
        commands.append(f"draw {args.draw}")

    for spec in args.ckey:
        commands.append(f"ckey {spec}")

    for spec in args.label:
        commands.append(f"label {spec}")

    for raw in args.cmd:
        commands.append(raw)

    commands.append("pl")
    commands.append(f"save {tmp_ps}")

    return commands


# ── rich command display ───────────────────────────────────────────────────────

def _print_commands(commands: list[str], gui: bool) -> None:
    body = Text()
    for i, cmd in enumerate(commands):
        parts = cmd.split(None, 1)
        body.append(parts[0], style="cmd.key")
        if len(parts) > 1:
            body.append(" ")
            body.append(parts[1], style="cmd.val")
        if i < len(commands) - 1:
            body.append("\n")
    subtitle = "exit" if not gui else "interactive — type exit to quit"
    console.print(Panel(
        body,
        title="[bold]jplotter commands[/bold]",
        subtitle=f"[hint]{subtitle}[/hint]",
        border_style="bright_black",
        padding=(0, 1),
    ))


# ── jplotter runner ────────────────────────────────────────────────────────────

def run_jplotter(commands: list[str], jplotter: str, timeout: int,
                 dry_run: bool, gui: bool,
                 env: Optional[dict[str, str]] = None) -> int:
    _print_commands(commands, gui)
    if dry_run:
        return 0
    if shutil.which(jplotter) is None:
        console.print(f"[status.err]ERROR:[/status.err] cannot find jplotter executable: {jplotter}")
        return 127

    log_path = Path.cwd() / "jplotter.last"
    with open(log_path, "w", encoding="utf-8") as log:
        child = pexpect.spawn(jplotter, encoding="utf-8", timeout=timeout, env=env)
        child.logfile = log
        child.expect("jcli>")

        for cmd in commands:
            child.sendline(cmd)
            child.expect("jcli>")

        if gui:
            child.interact()
        else:
            child.sendline("exit")
            child.expect(pexpect.EOF)

    return child.exitstatus or 0


# ── entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="CLI wrapper around jplotter/jiveplot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # positional
    parser.add_argument("vis",    help="Measurement Set path")
    parser.add_argument("mode",   nargs="?", default="plot",
        choices=["plot", "vplot", "radplot", "projplot", "uvplot", "wtplot"],
        help="Difmap-like plot alias")
    parser.add_argument("output", nargs="?",
        help="Output file — extension sets format: .ps  .pdf  .png  .jpg  .tiff")
    parser.add_argument("count",  nargs="?", type=int,
        help="Number of plot rows, e.g. vplot 4")

    # data selection
    parser.add_argument("-x", default="amp",  help="quantity: amp phase real imag wt")
    parser.add_argument("-y", default="time", help="axis: time freq uvdist chan")
    parser.add_argument("-field", "--field", default="", help="Source/field selection")
    parser.add_argument("--nxy",   default=None, help="Plot layout NxM, e.g. 2x3")
    parser.add_argument("--iterate", "--iter",
        choices=["baseline", "antenna", "field", "source", "none"], default="none")
    parser.add_argument("--select", action="append", default=[],
        help="Raw jiveplot selection command(s). Repeatable; ';' joins multiple.")

    # appearance
    parser.add_argument("--theme",
        choices=list(_THEME_COMMANDS), default="classic",
        help=(
            "classic: jplotter defaults.  "
            "modern: draw both + linew 2.  "
            "publication: draw lines + linew 3.  "
            "dark: modern palette + GS/Pillow colour inversion."
        ),
    )
    parser.add_argument("--draw", default=None, metavar="STYLE",
        help=(
            "Drawing style (overrides --theme). "
            "Values: lines  points  both. "
            "Panel-qualified: 'amplitude:lines phase:points'."
        ),
    )
    parser.add_argument("--show-flags", action="store_true",
        help=(
            "Show flagged data overlaid (jiveplot 'show both'). "
            "Flagged points use PGPLOT symbol 5 (×) and are drawn in dark "
            "foreground colour instead of the data-set colour."
        ),
    )
    parser.add_argument("--ckey", action="append", default=[], metavar="EXPR",
        help=(
            "Colour-key expression (jiveplot ckey). Repeatable. "
            "Default: even subbands colour 8, odd subbands colour 3. "
            "Examples: 'p'  'p[rr]=2 p[ll]=3'  'bl'  'sb[0,2,4]=2 sb[1,3,5]=3'."
        ),
    )
    parser.add_argument("--label", action="append", default=[], metavar="SPEC",
        help=(
            "Axis label (jiveplot label). Repeatable. "
            "Syntax: axis:'text'. PGPLOT escapes work (\\\\gF=Φ). "
            "Examples: \"x:'Time (UTC)'\"  \"phase:'\\\\gF (deg)'\"."
        ),
    )
    parser.add_argument("--cmd", action="append", default=[], metavar="CMD",
        help=(
            "Raw jiveplot command passthrough, appended just before 'pl'. "
            "Repeatable. "
            "Examples: --cmd 'avt scalar'  --cmd 'solint 30s'  --cmd 'y0 local'."
        ),
    )

    # output
    parser.add_argument("--dpi", type=int, default=150,
        help="DPI for raster output (png/jpg/tiff). Default: 150.")
    parser.add_argument("--preview", action="store_true",
        help=(
            "Show a terminal image preview after plotting. "
            "Uses the output PNG if available; otherwise renders a temp PNG. "
            "Requires chafa, viu, or timg."
        ),
    )

    # interactive / plumbing
    parser.add_argument("--gui", action="store_true",
        help="Keep the jplotter window open for interactive use.")
    parser.add_argument("--list", action="store_true",
        help="List jplotter commands/plot types and exit.")
    parser.add_argument("--jplotter", default="jplotter", help="jplotter executable.")
    parser.add_argument("--timeout",  type=int, default=120)
    parser.add_argument("--dry-run",  action="store_true")

    args = parser.parse_args()

    if args.mode == "projplot":
        return _run_projplot_anpuv(args)

    # ── always route through a temp PS ──────────────────────────────────────
    # jplotter writes PS; all format conversion and post-processing happens here.

    fd, tmp_ps = tempfile.mkstemp(suffix=".ps")
    os.close(fd)
    ps_consumed = False  # True once moved to a .ps output

    try:
        commands = build_commands(args, tmp_ps)
        if args.show_flags and not args.dry_run:
            with tempfile.TemporaryDirectory(prefix="msinspect-jplotter-") as patch_dir:
                env = _with_jiveplot_sitecustomize(
                    os.environ, patch_dir, dark_flags=True
                )
                rc = run_jplotter(
                    commands, args.jplotter, args.timeout, args.dry_run, args.gui,
                    env=env,
                )
        else:
            rc = run_jplotter(
                commands, args.jplotter, args.timeout, args.dry_run, args.gui
            )

        if rc != 0 or args.dry_run:
            return rc

        # ── format conversion ────────────────────────────────────────────────
        if args.output:
            output_ext = Path(args.output).suffix.lower()

            if output_ext == ".ps":
                shutil.move(tmp_ps, args.output)
                ps_consumed = True
                console.print(f"[status.ok]Saved:[/status.ok] [bold]{args.output}[/bold]")

            else:
                ok = _convert_output(tmp_ps, args.output, args.dpi)
                if ok and args.theme == "dark":
                    _apply_dark(args.output)
                if ok and output_ext == ".pdf":
                    _add_pdf_metadata(
                        args.output, args.vis,
                        _resolve_plot_type(args), args.field,
                    )

        # ── terminal preview ─────────────────────────────────────────────────
        if args.preview:
            output_ext = Path(args.output).suffix.lower() if args.output else ""
            if output_ext == ".png":
                _terminal_preview(args.output)
            else:
                # Derive preview PNG from the temp PS (still alive) or the
                # moved .ps output file.
                ps_src = args.output if ps_consumed else tmp_ps
                fd2, prev_png = tempfile.mkstemp(suffix=".png")
                os.close(fd2)
                try:
                    if _convert_output(ps_src, prev_png, min(args.dpi, 150)):
                        _terminal_preview(prev_png)
                finally:
                    Path(prev_png).unlink(missing_ok=True)

    finally:
        if not ps_consumed:
            Path(tmp_ps).unlink(missing_ok=True)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())

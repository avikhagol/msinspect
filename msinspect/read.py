from pathlib import Path
from casacore.tables import table
from casacore.quanta import quantity


def _format_table_value(value, *, max_width=80):
    if hasattr(value, "shape"):
        shape = tuple(value.shape)
        size = getattr(value, "size", 0)

        if size == 0:
            text = f"array{shape}"
        elif size <= 8:
            text = str(value.tolist())
        else:
            sample = value.ravel()[:4].tolist()
            text = f"array{shape} {sample} ..."
    elif isinstance(value, (list, tuple)):
        if len(value) > 8:
            text = f"{type(value).__name__}({len(value)}) {list(value[:4])} ..."
        else:
            text = str(value)
    else:
        text = str(value)

    if len(text) > max_width:
        return text[: max_width - 3] + "..."

    return text


def _has_value(value):
    if value is None:
        return False

    if hasattr(value, "size"):
        return value.size > 0

    if isinstance(value, (str, bytes, list, tuple, dict, set)):
        return len(value) > 0

    return True


def read_ms_table(ms_path, *, max_rows=20, start_row=0, columns=None):
    ms_path = Path(ms_path)
    start_row = max(0, start_row)

    with table(str(ms_path), readonly=True, ack=False) as t:
        available_columns = t.colnames()
        selected_columns = list(columns or available_columns)
        unknown_columns = sorted(set(selected_columns) - set(available_columns))

        if unknown_columns:
            raise ValueError(
                "Unknown column(s): "
                + ", ".join(unknown_columns)
                + ". Available columns: "
                + ", ".join(available_columns)
            )

        nrows = t.nrows()
        rows = []
        row_indices = []
        non_empty_columns = set()
        stop_row = min(start_row + max_rows, nrows)

        for row_index in range(start_row, stop_row):
            row = {}
            for column in selected_columns:
                try:
                    value = t.getcell(column, row_index)
                except Exception:
                    continue

                if not _has_value(value):
                    continue

                row[column] = _format_table_value(value)
                non_empty_columns.add(column)

            if row:
                rows.append(row)
                row_indices.append(row_index)

    rendered_columns = [
        column for column in selected_columns
        if column in non_empty_columns
    ]

    return {
        "abs_path": ms_path.absolute(),
        "name": ms_path.name,
        "nrows": nrows,
        "start_row": start_row,
        "end_row": stop_row,
        "shown_rows": len(rows),
        "columns": rendered_columns,
        "rows": rows,
        "row_indices": row_indices,
    }


def ms_summary(ms_path):
    ms_path = Path(ms_path)

    summary = {}

    with table(str(ms_path), readonly=True, ack=False) as t:
        summary["abs_path"] = ms_path.absolute()
        summary["name"] = ms_path.name
        summary["nrows"] = t.nrows()
        summary["columns"] = t.colnames()

        kws = t.getkeywords()

        # detect subtables
        subtables = {
            k: v
            for k, v in kws.items()
            if isinstance(v, str) and "Table:" in v
        }

        summary["subtables"] = list(subtables.keys())

    obs_path = ms_path / "OBSERVATION"
    if obs_path.exists():
        with table(str(obs_path), readonly=True, ack=False) as obsn:
            if "TELESCOPE_NAME" in obsn.colnames():
                summary['telescope'] = obsn.getcell("TELESCOPE_NAME", 0)
            if "OBSERVER" in obsn.colnames():
                summary['observer'] = obsn.getcell("OBSERVER", 0)
                if "PROJECT" in obsn.colnames():
                    summary['project'] = obsn.getcell("PROJECT", 0)

            if "TIME_RANGE" in obsn.colnames():
                timerange = obsn.getcell("TIME_RANGE", 0)
                if len(timerange) == 2:
                    st, et = timerange
                    td = et-st
                    summary['start_time'] = quantity(st, 's').formatted("YMD")
                    summary['end_time'] = quantity(et, 's').formatted("YMD")
                    hours = int(td // 3600)
                    minutes = int((td % 3600) // 60)
                    seconds = td % 60

                    summary['obs_length'] = f"{hours:02d}h{minutes:02d}m{seconds:05.2f}s"



    # --------------------------------------
    ant_path = ms_path / "ANTENNA"
    if ant_path.exists():
        with table(str(ant_path), readonly=True, ack=False) as ant:
            summary["nantennas"] = ant.nrows()

            if "NAME" in ant.colnames():
                summary["antennas"] = ant.getcol("NAME")

    # --------------------------------------
    field_path = ms_path / "FIELD"
    if field_path.exists():
        with table(str(field_path), readonly=True, ack=False) as fld:
            summary["nfields"] = fld.nrows()

            if "NAME" in fld.colnames():
                summary["fields"] = fld.getcol("NAME")

    # --------------------------------------
    spw_path = ms_path / "SPECTRAL_WINDOW"
    if spw_path.exists():
        with table(str(spw_path), readonly=True, ack=False) as spw:
            summary["nspw"] = spw.nrows()

            if "NUM_CHAN" in spw.colnames():
                summary["nchan"] = spw.getcol("NUM_CHAN")
            if "CHAN_FREQ" in spw.colnames():
                summary["spw_info"] = [(i, f"{spw.getcell('CHAN_FREQ', i).mean()/1e9:.2f} GHz") for i in range(spw.nrows())]


    # --------------------------------------  Polarization
    pol_path = ms_path / "POLARIZATION"
    if pol_path.exists():
        with table(str(pol_path), readonly=True, ack=False) as pol:
            summary["npol_setup"] = pol.nrows()

            if "CORR_TYPE" in pol.colnames():
                summary["corr_types"] = [
                    list(pol.getcell("CORR_TYPE", i))
                    for i in range(pol.nrows())
                ]

    return summary

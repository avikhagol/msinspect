from pathlib import Path
from casacore.tables import table



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
        with table(str(obs_path), readonly=True, ack=False) as ant:
            if "TELESCOPE_NAME" in ant.colnames():
                summary['telescope'] = ant.getcell("TELESCOPE_NAME", 0)

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
                summary["corr_types"] = pol.getcol("CORR_TYPE")

    return summary
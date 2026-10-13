"""platelib - reusable helpers for plate-based assay data.

Everything works on a tidy pandas DataFrame with one row per well per read:
    well, row, col, time, value  (+ sample, replicate once a layout is attached)

Typical use (script or notebook):
    import platelib as pl
    data   = pl.load_data("export.csv", fmt="long")
    layout = pl.make_layout({"Control": "A1:A3", "Drug": ["B1:B3", "C1"]})
    df     = pl.attach_layout(data, layout)
    pl.plot_grouped(df, "curves")
"""
from __future__ import annotations

import re
import string
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb

PLATE_SHAPES = {6: (2, 3), 12: (3, 4), 24: (4, 6), 48: (6, 8), 96: (8, 12), 384: (16, 24)}
PLOT_TYPES = ["curves", "bar", "box", "heatmap"]
PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]
# Same colors as PALETTE, with human-readable names for UI dropdowns.
COLOR_CHOICES = {
    "Blue": "#1f77b4",
    "Orange": "#ff7f0e",
    "Green": "#2ca02c",
    "Red": "#d62728",
    "Purple": "#9467bd",
    "Brown": "#8c564b",
    "Pink": "#e377c2",
    "Gray": "#7f7f7f",
    "Olive": "#bcbd22",
    "Teal": "#17becf",
}
_WELL_RE = re.compile(r"^([A-Za-z])0*(\d+)$")


# --------------------------------------------------------------------------- wells
def plate_shape(n_wells: int = 96) -> tuple[int, int]:
    return PLATE_SHAPES[int(n_wells)]


def parse_well(well: str) -> tuple[int, int]:
    """'B3' or 'B03' -> (row=1, col=2), zero-based."""
    m = _WELL_RE.match(str(well).strip())
    if not m:
        raise ValueError(f"Bad well name: {well!r}")
    return string.ascii_uppercase.index(m.group(1).upper()), int(m.group(2)) - 1


def well_name(row: int, col: int) -> str:
    return f"{string.ascii_uppercase[row]}{col + 1}"


def all_wells(n_wells: int = 96) -> list[str]:
    nr, nc = plate_shape(n_wells)
    return [well_name(r, c) for r in range(nr) for c in range(nc)]


def expand_wells(spec: str, n_wells: int = 96) -> list[str]:
    """'A1:A3, B1, C1:D2' -> list of well names. Ranges are rectangles ('-' also works)."""
    nr, nc = plate_shape(n_wells)
    wells: list[str] = []
    for tok in re.split(r"[,;]", spec):
        tok = tok.strip()
        if not tok:
            continue
        parts = re.split(r"[:\-]", tok)
        if len(parts) > 2:
            raise ValueError(f"Bad well range: {tok!r}")
        (r0, c0), (r1, c1) = [parse_well(p) for p in (parts[0], parts[-1])]
        r_lo, r_hi = sorted((r0, r1))
        c_lo, c_hi = sorted((c0, c1))
        if r_hi >= nr or c_hi >= nc:
            raise ValueError(f"{tok!r} is outside a {n_wells}-well plate")
        wells += [well_name(r, c) for r in range(r_lo, r_hi + 1) for c in range(c_lo, c_hi + 1)]
    return wells


# --------------------------------------------------------------------------- layout
def make_layout(groups: dict, n_wells: int = 96) -> pd.DataFrame:
    """groups: {"sample name": "A1:A3, B1"  or  ["A1:A3", "B1"]} -> layout DataFrame."""
    rows, seen = [], {}
    for sample, spec in groups.items():
        specs = [spec] if isinstance(spec, str) else list(spec)
        for w in (w for s in specs for w in expand_wells(s, n_wells)):
            if w in seen:
                raise ValueError(f"Well {w} assigned to both {seen[w]!r} and {sample!r}")
            seen[w] = sample
            r, c = parse_well(w)
            rows.append({"well": w, "row": r, "col": c, "sample": sample})
    layout = pd.DataFrame(rows, columns=["well", "row", "col", "sample"])
    layout["replicate"] = layout.groupby("sample").cumcount() + 1
    return layout


def parse_layout_text(text: str, n_wells: int = 96) -> pd.DataFrame:
    """One sample per line, 'Name: wells'. '#' starts a comment. Repeated names are merged."""
    groups: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Expected 'Name: wells', got {line!r}")
        name, spec = line.split(":", 1)
        groups.setdefault(name.strip(), []).append(spec)
    return make_layout(groups, n_wells)


def layout_from_file(path: str | Path, n_wells: int = 96) -> pd.DataFrame:
    """CSV/XLSX with columns 'well' and 'sample' (any extra columns are kept, e.g. dose)."""
    t = _read_table(path)
    t.columns = [str(c).lower() for c in t.columns]
    t["well"] = t["well"].map(lambda w: well_name(*parse_well(w)))
    t["row"], t["col"] = zip(*t["well"].map(parse_well))
    t["replicate"] = t.groupby("sample").cumcount() + 1
    return t


def assign_wells(groups: dict, name: str, wells: list[str], color: str | None = None) -> dict:
    """Return a new groups dict with the selected wells assigned to a named group."""
    groups = dict(groups)
    wells = [well_name(*parse_well(w)) for w in wells]
    if not name or not wells:
        return groups
    # Keep notes already saved under this name (the loop below can drop the group first).
    notes = groups.get(name, {}).get("notes", "")
    seen = set()
    for key, info in list(groups.items()):
        info = dict(info)
        kept = [w for w in info.get("wells", []) if w not in wells]
        if kept:
            info["wells"] = kept
            groups[key] = info
        else:
            groups.pop(key, None)
        seen.update(kept)
    groups[name] = {
        "wells": sorted(set(wells), key=lambda w: (parse_well(w)[0], parse_well(w)[1])),
        "color": color or PALETTE[0],
        "notes": notes,
    }
    return groups


def remove_group(groups: dict, name: str) -> dict:
    return {k: v for k, v in groups.items() if k != name}


def apply_group_edits(groups: dict, edits: list) -> dict:
    """Rename groups and set their notes. `edits` is [(old_name, new_name, notes), ...].

    Wells and colors are kept. A blank new name keeps the old one, and a rename that would
    collide with another group's name is ignored (so no group is ever overwritten).
    """
    from collections import Counter

    notes = {old: (n or "") for old, _new, n in edits}
    names = {old: ((new or "").strip() or old) for old, new, _n in edits}
    names = {old: names.get(old, old) for old in groups}
    for _ in range(len(names) + 1):
        counts = Counter(names.values())
        clash = [old for old, new in names.items() if new != old and counts[new] > 1]
        if not clash:
            break
        for old in clash:
            names[old] = old
    out = {}
    for old, info in groups.items():
        info = dict(info)
        if old in notes:
            info["notes"] = notes[old]
        out[names[old]] = info
    return out


def layout_from_groups(groups: dict, n_wells: int = 96) -> pd.DataFrame:
    """Convert selected groups into a layout DataFrame compatible with `attach_layout`."""
    rows = []
    for name, info in groups.items():
        for well in info.get("wells", []):
            row, col = parse_well(well)
            rows.append({"well": well, "row": row, "col": col, "sample": name})
    if not rows:
        return pd.DataFrame(columns=["well", "row", "col", "sample", "replicate"])
    layout = pd.DataFrame(rows)
    layout["replicate"] = layout.groupby("sample").cumcount() + 1
    return layout.sort_values(["sample", "well"]).reset_index(drop=True)


def plate_table(n_wells: int = 96, groups: dict | None = None) -> pd.DataFrame:
    """Return a plate-like table with one row per well and assigned group label."""
    groups = groups or {}
    nr, nc = plate_shape(n_wells)
    rows = []
    for row in range(nr):
        for col in range(nc):
            well = well_name(row, col)
            group = "(unassigned)"
            for name, info in groups.items():
                if well in info.get("wells", []):
                    group = name
                    break
            rows.append({"well": well, "row": row, "col": col, "group": group})
    return pd.DataFrame(rows)


def to_readable(name: str, contents: bytes):
    """Wrap uploaded file bytes as a file-like object the loaders can read (keeps the extension)."""
    import io

    buf = io.BytesIO(contents)
    buf.name = name
    return buf


def excel_sheet_names(path) -> list[str]:
    """Return available sheet names for Excel inputs, or [] if unavailable."""
    if not path:
        return [""]
    if isinstance(path, (str, Path)):
        p = Path(path)
        if not p.exists() or p.suffix.lower() not in {".xlsx", ".xls"}:
            return [""]
        src = p
    else:
        name = getattr(path, "name", "")
        if Path(str(name)).suffix.lower() not in {".xlsx", ".xls"}:
            return [""]
        src = path
    try:
        return pd.ExcelFile(src).sheet_names
    except Exception:
        return [""]


# --------------------------------------------------------------------------- loading
def _suffix_of(src) -> str:
    """File extension for a path/Path, or for a file-like object carrying a .name."""
    name = src if isinstance(src, (str, Path)) else getattr(src, "name", "")
    return Path(str(name)).suffix.lower()


def _read_table(src, **kw) -> pd.DataFrame:
    if isinstance(src, pd.DataFrame):
        return src.copy()
    if _suffix_of(src) in {".xlsx", ".xls"}:
        return pd.read_excel(src, **kw)
    return pd.read_csv(src, **kw)


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["well"] = df["well"].map(lambda w: well_name(*parse_well(w)))
    rc = df["well"].map(parse_well)
    df["row"] = [r for r, _ in rc]
    df["col"] = [c for _, c in rc]
    if "time" not in df:
        df["time"] = np.nan
    first = ["well", "row", "col", "time", "value"]
    return df[first + [c for c in df.columns if c not in first]].reset_index(drop=True)


def load_long(src, well="Well", time="Time", value="Value", **kw) -> pd.DataFrame:
    """Long/tidy export: one row per well per read. Set time=None for endpoint data."""
    t = _read_table(src, **kw)
    columns = {str(c).strip().lower(): c for c in t.columns}
    well_col = columns.get(str(well).strip().lower(), well)
    value_col = columns.get(str(value).strip().lower(), value)
    ren = {well_col: "well", value_col: "value"}
    if time:
        time_col = columns.get(str(time).strip().lower(), time)
        ren[time_col] = "time"
    return _finish(t.rename(columns=ren))


def load_spectra(src, **kw) -> pd.DataFrame:
    """Load spectral exports with one well per column and wavelength per row."""
    if isinstance(src, pd.DataFrame):
        t = src.copy()
    elif _suffix_of(src) in {".xlsx", ".xls"}:
        raw = pd.read_excel(src, header=None, **kw)
        header_row = next(
            (
                i
                for i, row in raw.iterrows()
                if sum(_WELL_RE.match(str(value).strip()) is not None for value in row) >= 2
            ),
            None,
        )
        if header_row is None:
            return load_long(src, **kw)
        t = raw.iloc[header_row + 1 :].copy()
        t.columns = raw.iloc[header_row].tolist()
    else:
        t = _read_table(src, **kw)

    well_columns = [c for c in t.columns if _WELL_RE.match(str(c).strip())]

    if not well_columns:
        return load_long(t, **kw)

    id_columns = [c for c in t.columns if c not in well_columns]
    time_col = next(
        (c for c in id_columns if pd.to_numeric(t[c], errors="coerce").notna().any()),
        id_columns[0] if id_columns else None,
    )
    long = t.melt(
        id_vars=[time_col] if time_col is not None else [],
        value_vars=well_columns,
        var_name="well",
        value_name="value",
    )
    if time_col is not None:
        long = long.rename(columns={time_col: "time"})
    return _finish(long)


def _tecan_spectral_sections(raw: pd.DataFrame) -> list[tuple[str, int]]:
    sections = []
    labels = []
    for i, value in raw.iloc[:, 0].items():
        text = str(value).strip()
        if text.lower().startswith("label:"):
            labels.append((i, text.split(":", 1)[1].strip() or f"Scan {len(labels) + 1}"))
        if text.lower() != "wavel.":
            continue
        label = next((name for row, name in reversed(labels) if row < i), f"Scan {len(sections) + 1}")
        if any(existing == label for existing, _ in sections):
            label = f"{label} #{sum(existing.startswith(label) for existing, _ in sections) + 1}"
        sections.append((label, i))
    return sections


def _tecan_plate_scans(raw: pd.DataFrame) -> list[tuple[str, int]]:
    labels = []
    sections = []
    for index, value in raw.iloc[:, 0].items():
        text = str(value).strip()
        if text.lower().startswith("label:"):
            labels.append((index, text.split(":", 1)[1].strip()))
        if text != "<>":
            continue
        columns = [
            (column, int(number))
            for column, value in enumerate(raw.iloc[index, 1:], start=1)
            if pd.notna(number := pd.to_numeric(value, errors="coerce"))
            and float(number).is_integer()
            and 1 <= number <= 24
        ]
        if len(columns) < 2:
            continue
        end = next(
            (
                row
                for row in range(index + 1, len(raw))
                if str(raw.iloc[row, 0]).strip().lower() == "end time:"
            ),
            len(raw),
        )
        well_rows = [
            row
            for row in range(index + 1, end)
            if re.fullmatch(r"[A-P]", str(raw.iloc[row, 0]).strip(), flags=re.IGNORECASE)
        ]
        if len(well_rows) < 2:
            continue
        label = next(
            (name for row, name in reversed(labels) if row < index and name),
            f"Plate scan {len(sections) + 1}",
        )
        if any(existing == label for existing, _ in sections):
            label = f"{label} #{sum(existing.startswith(label) for existing, _ in sections) + 1}"
        sections.append((label, index))
    return sections


def tecan_measurement_names(src, **kw) -> list[str]:
    """List kinetic, spectral, and endpoint plate-scan measurements in a Tecan sheet."""
    raw = _read_table(src, header=None, **kw)
    if raw.empty or raw.shape[1] == 0:
        return []
    measurements = [
        (f"Wavelength scan — {label}", header)
        for label, header in _tecan_spectral_sections(raw)
    ]
    measurements.extend(
        (f"Plate scan — {label}", header)
        for label, header in _tecan_plate_scans(raw)
    )
    kinetic_row = next(
        (
            i
            for i, value in raw.iloc[:, 0].items()
            if re.fullmatch(r"time\s*\[s\]", str(value).strip(), flags=re.IGNORECASE)
        ),
        None,
    )
    if kinetic_row is not None:
        measurements.append(("Kinetic measurement", kinetic_row))
    return [name for name, _ in sorted(measurements, key=lambda item: item[1])]


def load_tecan(src, measurement=None, **kw) -> pd.DataFrame:
    """Load a selected kinetic, wavelength-scan, or endpoint plate-scan measurement."""
    raw = _read_table(src, header=None, **kw)
    if raw.empty or raw.shape[1] == 0:
        raise ValueError("The selected Tecan worksheet is empty.")
    time_row = next(
        (
            i
            for i, value in raw.iloc[:, 0].items()
            if re.fullmatch(r"time\s*\[s\]", str(value).strip(), flags=re.IGNORECASE)
        ),
        None,
    )
    selected = measurement or ("Kinetic measurement" if time_row is not None else None)
    if selected == "Kinetic measurement" and time_row is not None:
        times = pd.to_numeric(raw.iloc[time_row, 1:], errors="coerce")
        well_rows = [
            (i, str(value).strip().upper())
            for i, value in raw.iloc[time_row + 1 :, 0].items()
            if _WELL_RE.fullmatch(str(value).strip())
        ]
        rows = [
            {"well": well, "time": time, "value": value, "measurement": selected}
            for row_index, well in well_rows
            for time, value in zip(
                times,
                pd.to_numeric(raw.iloc[row_index, 1 : len(times) + 1], errors="coerce"),
            )
            if pd.notna(time)
        ]
        if not rows:
            raise ValueError("No kinetic well readings were found below the Tecan 'Time [s]' row.")
        result = _finish(pd.DataFrame(rows))
        result.attrs["x_label"] = "time (s)"
        return result

    scans = _tecan_plate_scans(raw)
    scan = next(
        (
            (label, header)
            for label, header in scans
            if selected in {label, f"Plate scan — {label}"}
        ),
        None,
    )
    if scan is not None:
        label, header = scan
        columns = [
            (column, int(number))
            for column, value in enumerate(raw.iloc[header, 1:], start=1)
            if pd.notna(number := pd.to_numeric(value, errors="coerce"))
            and float(number).is_integer()
            and number > 0
        ]
        end = next(
            (
                row
                for row in range(header + 1, len(raw))
                if str(raw.iloc[row, 0]).strip().lower() == "end time:"
            ),
            len(raw),
        )
        rows = []
        for row_index in range(header + 1, end):
            row_label = str(raw.iloc[row_index, 0]).strip().upper()
            if not re.fullmatch(r"[A-P]", row_label):
                continue
            for column, well_column in columns:
                value = pd.to_numeric(raw.iloc[row_index, column], errors="coerce")
                if pd.notna(value):
                    rows.append(
                        {
                            "well": f"{row_label}{well_column}",
                            "value": value,
                            "measurement": label,
                        }
                    )
        if not rows:
            raise ValueError(f"No plate readings were found for Tecan measurement {label!r}.")
        result = _finish(pd.DataFrame(rows))
        result.attrs["x_label"] = "endpoint"
        return result

    sections = _tecan_spectral_sections(raw)
    if not sections:
        raise ValueError("Tecan report is missing a supported kinetic, spectral, or plate-scan table.")
    selected = selected or sections[0][0]
    section = next(
        (
            (label, header)
            for label, header in sections
            if selected in {label, f"Wavelength scan — {label}"}
        ),
        None,
    )
    if section is None:
        raise ValueError(f"Unknown Tecan measurement: {selected!r}")

    label, header = section
    wavelengths = pd.to_numeric(raw.iloc[header, 1:], errors="coerce")
    end = next(
        (i for i in range(header + 1, len(raw)) if str(raw.iloc[i, 0]).strip().lower() == "end time:"),
        len(raw),
    )
    rows = []
    for row_index in range(header + 1, end):
        well_value = raw.iloc[row_index, 0]
        if pd.isna(well_value) or not _WELL_RE.fullmatch(str(well_value).strip()):
            continue
        values = pd.to_numeric(raw.iloc[row_index, 1 : len(wavelengths) + 1], errors="coerce")
        rows.extend(
            {
                "well": str(well_value).strip().upper(),
                "time": wavelength,
                "value": value,
                "measurement": label,
            }
            for wavelength, value in zip(wavelengths, values)
            if pd.notna(wavelength)
        )
    if not rows:
        raise ValueError(f"No wavelength readings were found for Tecan measurement {label!r}.")
    result = _finish(pd.DataFrame(rows))
    result.attrs["x_label"] = "wavelength (nm)"
    return result


def load_wide(src, well="Well", **kw) -> pd.DataFrame:
    """Wells as rows, one column per time point (column headers = times)."""
    t = _read_table(src, **kw).rename(columns={well: "well"})
    time_cols = [c for c in t.columns if c != "well" and pd.notna(pd.to_numeric(c, errors="coerce"))]
    long = t.melt(id_vars="well", value_vars=time_cols, var_name="time", value_name="value")
    long["time"] = pd.to_numeric(long["time"])
    return _finish(long)


def load_matrix(src, **kw) -> pd.DataFrame:
    """Endpoint read laid out like the plate: row letters down the side, column numbers across."""
    t = _read_table(src, index_col=0, **kw)
    s = t.stack().rename("value").reset_index()
    s.columns = ["r", "c", "value"]
    s["well"] = s["r"].astype(str) + s["c"].astype(int).astype(str)
    return _finish(s[["well", "value"]])


def load_data(src, fmt: str = "long", **kw) -> pd.DataFrame:
    fmt = (fmt or "long").lower()
    return {
        "long": load_long,
        "spectra": load_spectra,
        "wide": load_wide,
        "matrix": load_matrix,
        "tecan": load_tecan,
    }[fmt](src, **kw)


def attach_layout(data: pd.DataFrame, layout: pd.DataFrame) -> pd.DataFrame:
    """Add sample/replicate (and any extra layout columns) to the data; unassigned wells are dropped."""
    extra = [c for c in layout.columns if c not in {"row", "col"}]
    return data.merge(layout[extra], on="well", how="inner").sort_values(["sample", "well", "time"]).reset_index(drop=True)


# --------------------------------------------------------------------------- summaries
def endpoint(df: pd.DataFrame, time: float | None = None) -> pd.DataFrame:
    """Rows at one time point (nearest to `time`, default last). No-op for endpoint-only data."""
    if df["time"].isna().all():
        return df.copy()
    times = df["time"].dropna().unique()
    t = times.max() if time is None else times[np.abs(times - time).argmin()]
    return df[df["time"] == t].copy()


def summarize(df: pd.DataFrame, by=("sample", "time")) -> pd.DataFrame:
    """mean / sd / sem / n of `value` per group."""
    out = df.groupby(list(by), dropna=False)["value"].agg(mean="mean", sd="std", n="count").reset_index()
    out["sem"] = out["sd"] / np.sqrt(out["n"])
    return out


def summarize_curves(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize the values making up each group's curve."""
    if df.empty:
        return pd.DataFrame(columns=["sample", "mean", "median", "std"])
    return (
        df.groupby("sample", sort=False)["value"]
        .agg(mean="mean", median="median", std="std")
        .reset_index()
    )


# --------------------------------------------------------------------------- plots
def plot_plate_heatmap(df, n_wells=96, time=None, cmap="viridis"):
    d = endpoint(df, time)
    nr, nc = plate_shape(n_wells)
    grid = np.full((nr, nc), np.nan)
    grid[d["row"].to_numpy(), d["col"].to_numpy()] = d["value"].to_numpy()
    fig, ax = plt.subplots(figsize=(1 + nc * 0.55, 1 + nr * 0.55))
    im = ax.imshow(grid, cmap=cmap)
    ax.set_xticks(range(nc), labels=[str(i + 1) for i in range(nc)])
    ax.set_yticks(range(nr), labels=list(string.ascii_uppercase[:nr]))
    fig.colorbar(im, ax=ax, label="value")
    return fig


def plot_curves(df, facet=False, ncols=3, err="sd", xlabel="time", colors=None, trace_mode="average"):
    if df["time"].isna().all():
        raise ValueError("No time column in this data - use 'bar', 'box' or 'heatmap'.")
    if trace_mode not in {"average", "individual", "both"}:
        raise ValueError("trace_mode must be 'average', 'individual', or 'both'.")
    samples = list(df["sample"].unique())
    colors = colors or {}
    stats = summarize(df).sort_values("time")
    if facet:
        nc = min(ncols, len(samples))
        nr = -(-len(samples) // nc)
        fig, axes = plt.subplots(nr, nc, figsize=(4 * nc, 3 * nr), sharex=True, sharey=True, squeeze=False)
        for ax, s in zip(axes.flat, samples):
            for _, w in df[df["sample"] == s].groupby("well"):
                ax.plot(w["time"], w["value"], color="gray", alpha=0.4, lw=0.8)
            st = stats[stats["sample"] == s]
            ax.plot(st["time"], st["mean"], lw=2, color=colors.get(s))
            ax.set_title(s)
        for ax in list(axes.flat)[len(samples):]:
            ax.axis("off")
    else:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        cycle_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        for sample_index, s in enumerate(samples):
            st = stats[stats["sample"] == s]
            color = colors.get(s) or cycle_colors[sample_index % len(cycle_colors)]
            x = pd.to_numeric(st["time"], errors="coerce").to_numpy(dtype=float)
            mean = pd.to_numeric(st["mean"], errors="coerce").to_numpy(dtype=float)
            if trace_mode != "individual":
                (line,) = ax.plot(x, mean, lw=2.5, label=s, color=color, zorder=4)
            if err and trace_mode != "individual":
                band = pd.to_numeric(st[err], errors="coerce").fillna(0).to_numpy(dtype=float)
                ax.fill_between(x, mean - band, mean + band, color=line.get_color(), alpha=0.2)
            if trace_mode != "average":
                rgb = to_rgb(color)
                wells = list(df.loc[df["sample"] == s, "well"].drop_duplicates().sort_values())
                lightness = np.linspace(0.48, 0.12, len(wells))
                shades = [
                    tuple(channel + (1 - channel) * amount for channel in rgb)
                    for amount in lightness
                ]
                for well_index, (well, well_data) in enumerate(
                    df.loc[df["sample"] == s].groupby("well", sort=True)
                ):
                    well_x = pd.to_numeric(well_data["time"], errors="coerce").to_numpy(dtype=float)
                    well_y = pd.to_numeric(well_data["value"], errors="coerce").to_numpy(dtype=float)
                    ax.plot(
                        well_x,
                        well_y,
                        color=shades[well_index],
                        alpha=0.85,
                        lw=0.9,
                        label=s if trace_mode == "individual" and well_index == 0 else "_nolegend_",
                        zorder=2,
                    )
        ax.set_xlabel(xlabel)
        ax.set_ylabel("value")
        ax.legend()
    fig.tight_layout()
    return fig


def plot_bars(df, time=None, colors=None):
    d = endpoint(df, time)
    samples = list(d["sample"].unique())
    colors = colors or {}
    st = summarize(d, by=("sample",)).set_index("sample").loc[samples]
    fig, ax = plt.subplots(figsize=(1.2 * len(samples) + 2, 4))
    x = np.arange(len(samples))
    for i, s in enumerate(samples):
        error = st.loc[s, "sd"]
        ax.bar(i, st.loc[s, "mean"], yerr=0 if pd.isna(error) else error, capsize=4, alpha=0.6, color=colors.get(s))
    rng = np.random.default_rng(0)
    for i, s in enumerate(samples):
        v = d.loc[d["sample"] == s, "value"]
        ax.scatter(i + rng.uniform(-0.12, 0.12, len(v)), v, color="k", s=14, zorder=3)
    ax.set_xticks(x, samples, rotation=30, ha="right")
    ax.set_ylabel("value")
    fig.tight_layout()
    return fig


def plot_box(df, time=None, colors=None):
    d = endpoint(df, time)
    samples = list(d["sample"].unique())
    colors = colors or {}
    fig, ax = plt.subplots(figsize=(1.2 * len(samples) + 2, 4))
    bp = ax.boxplot([d.loc[d["sample"] == s, "value"] for s in samples], patch_artist=True)
    for patch, s in zip(bp["boxes"], samples):
        patch.set_facecolor(colors.get(s, patch.get_facecolor()))
    ax.set_xticks(range(1, len(samples) + 1), samples, rotation=30, ha="right")
    ax.set_ylabel("value")
    fig.tight_layout()
    return fig


def plot_grouped(
    df,
    plot_type="curves",
    samples=None,
    facet=False,
    time=None,
    err="sd",
    n_wells=96,
    ncols=3,
    xlabel="time",
    colors=None,
    trace_mode="average",
):
    """One entry point: filter to `samples`, then draw `plot_type` ('curves','bar','box','heatmap')."""
    if samples:
        df = df[df["sample"].isin(samples)]
    if df.empty:
        raise ValueError("Nothing to plot - check the layout and sample selection.")
    if plot_type == "curves":
        return plot_curves(
            df,
            facet=facet,
            ncols=ncols,
            err=err,
            xlabel=xlabel,
            colors=colors,
            trace_mode=trace_mode,
        )
    if plot_type == "bar":
        return plot_bars(df, time, colors=colors)
    if plot_type == "box":
        return plot_box(df, time, colors=colors)
    if plot_type == "heatmap":
        return plot_plate_heatmap(df, n_wells, time)
    raise ValueError(f"Unknown plot_type {plot_type!r}; choose from {PLOT_TYPES}")


# --------------------------------------------------------------------------- demo
def demo_data(n_wells: int = 96, seed: int = 0) -> pd.DataFrame:
    """Synthetic kinetic read so the app runs before real data is loaded."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, 121, 10)
    rows = []
    for w in all_wells(n_wells):
        r, _ = parse_well(w)
        a = {0: 0.05, 1: 1.0, 2: 2.0, 3: 1.4}.get(r, 0.5)
        y = a / (1 + np.exp(-(t - 60) / 12)) + rng.normal(0, 0.03 * max(a, 0.2), len(t))
        rows += [{"well": w, "time": ti, "value": yi} for ti, yi in zip(t, y)]
    return _finish(pd.DataFrame(rows))


if __name__ == "__main__":
    df = attach_layout(demo_data(), make_layout({"Control": "B1:B3", "Drug": "C1:C3"}))
    print(df.head())
    print(summarize(df).head())

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

PLATE_SHAPES = {6: (2, 3), 12: (3, 4), 24: (4, 6), 48: (6, 8), 96: (8, 12), 384: (16, 24)}
PLOT_TYPES = ["curves", "bar", "box", "heatmap"]
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


# --------------------------------------------------------------------------- loading
def _read_table(src, **kw) -> pd.DataFrame:
    if isinstance(src, pd.DataFrame):
        return src.copy()
    p = Path(src)
    if p.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(p, **kw)
    return pd.read_csv(p, **kw)


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
    ren = {well: "well", value: "value"}
    if time:
        ren[time] = "time"
    return _finish(t.rename(columns=ren))


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
    return {"long": load_long, "wide": load_wide, "matrix": load_matrix}[fmt](src, **kw)


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


def plot_curves(df, facet=False, ncols=3, err="sd"):
    if df["time"].isna().all():
        raise ValueError("No time column in this data - use 'bar', 'box' or 'heatmap'.")
    samples = list(df["sample"].unique())
    stats = summarize(df).sort_values("time")
    if facet:
        nc = min(ncols, len(samples))
        nr = -(-len(samples) // nc)
        fig, axes = plt.subplots(nr, nc, figsize=(4 * nc, 3 * nr), sharex=True, sharey=True, squeeze=False)
        for ax, s in zip(axes.flat, samples):
            for _, w in df[df["sample"] == s].groupby("well"):
                ax.plot(w["time"], w["value"], color="gray", alpha=0.4, lw=0.8)
            st = stats[stats["sample"] == s]
            ax.plot(st["time"], st["mean"], lw=2)
            ax.set_title(s)
        for ax in list(axes.flat)[len(samples):]:
            ax.axis("off")
    else:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for s in samples:
            st = stats[stats["sample"] == s]
            (line,) = ax.plot(st["time"], st["mean"], lw=2, label=s)
            band = st[err].fillna(0)
            ax.fill_between(st["time"], st["mean"] - band, st["mean"] + band, color=line.get_color(), alpha=0.2)
        ax.set_xlabel("time")
        ax.set_ylabel("value")
        ax.legend()
    fig.tight_layout()
    return fig


def plot_bars(df, time=None):
    d = endpoint(df, time)
    samples = list(d["sample"].unique())
    st = summarize(d, by=("sample",)).set_index("sample").loc[samples]
    fig, ax = plt.subplots(figsize=(1.2 * len(samples) + 2, 4))
    x = np.arange(len(samples))
    ax.bar(x, st["mean"], yerr=st["sd"].fillna(0), capsize=4, alpha=0.6)
    rng = np.random.default_rng(0)
    for i, s in enumerate(samples):
        v = d.loc[d["sample"] == s, "value"]
        ax.scatter(i + rng.uniform(-0.12, 0.12, len(v)), v, color="k", s=14, zorder=3)
    ax.set_xticks(x, samples, rotation=30, ha="right")
    ax.set_ylabel("value")
    fig.tight_layout()
    return fig


def plot_box(df, time=None):
    d = endpoint(df, time)
    samples = list(d["sample"].unique())
    fig, ax = plt.subplots(figsize=(1.2 * len(samples) + 2, 4))
    ax.boxplot([d.loc[d["sample"] == s, "value"] for s in samples])
    ax.set_xticks(range(1, len(samples) + 1), samples, rotation=30, ha="right")
    ax.set_ylabel("value")
    fig.tight_layout()
    return fig


def plot_grouped(df, plot_type="curves", samples=None, facet=False, time=None, err="sd", n_wells=96, ncols=3):
    """One entry point: filter to `samples`, then draw `plot_type` ('curves','bar','box','heatmap')."""
    if samples:
        df = df[df["sample"].isin(samples)]
    if df.empty:
        raise ValueError("Nothing to plot - check the layout and sample selection.")
    if plot_type == "curves":
        return plot_curves(df, facet=facet, ncols=ncols, err=err)
    if plot_type == "bar":
        return plot_bars(df, time)
    if plot_type == "box":
        return plot_box(df, time)
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

import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import platelib as pl

    return mo, pl


@app.cell
def _(mo):
    _default_layout = """# Sample name: wells  (single wells or ranges, comma-separated)
Blank: A1:A3
Control: B1:B3
Drug A: C1:C3
Drug B: D1:D3
"""
    source = mo.ui.text(label="Data file (.csv/.xlsx; leave blank for demo data)", full_width=True)
    fmt = mo.ui.dropdown(["long", "wide", "matrix"], value="long", label="Data format")
    plate = mo.ui.dropdown({"96-well": 96, "384-well": 384}, value="96-well", label="Plate")
    layout_text = mo.ui.text_area(value=_default_layout, label="Plate layout", rows=8, full_width=True)
    mo.vstack([mo.md("# Plate explorer"), source, mo.hstack([fmt, plate]), layout_text])
    return fmt, layout_text, plate, source


@app.cell
def _(fmt, layout_text, pl, plate, source):
    # `data` = raw import, `layout` = well -> sample map, `df` = both joined.
    # All three are normal pandas DataFrames: use them in any new cell.
    _path = source.value.strip()
    data = pl.load_data(_path, fmt=fmt.value) if _path else pl.demo_data(plate.value)
    layout = pl.parse_layout_text(layout_text.value, n_wells=plate.value)
    df = pl.attach_layout(data, layout)
    return data, df, layout


@app.cell
def _(df, mo):
    mo.vstack(
        [
            mo.md(
                f"**{len(df)} rows, {df['sample'].nunique()} samples.** "
                "`data`, `layout` and `df` are ordinary DataFrames - add a cell to explore them."
            ),
            mo.ui.table(df, page_size=10),
        ]
    )
    return


@app.cell
def _(df, mo, pl):
    _samples = list(df["sample"].unique())
    _times = sorted(df["time"].dropna().unique())
    plot_type = mo.ui.dropdown(pl.PLOT_TYPES, value="curves", label="Plot type")
    chosen = mo.ui.multiselect(_samples, value=_samples, label="Samples")
    facet = mo.ui.checkbox(label="One panel per sample (curves)")
    err = mo.ui.dropdown(["sd", "sem"], value="sd", label="Error band")
    time_pick = (
        mo.ui.dropdown({f"{t:g}": t for t in _times}, value=f"{_times[-1]:g}", label="Time (bar/box/heatmap)")
        if _times
        else None
    )
    mo.hstack([c for c in (plot_type, chosen, facet, err, time_pick) if c is not None], justify="start")
    return chosen, err, facet, plot_type, time_pick


@app.cell
def _(chosen, df, err, facet, pl, plate, plot_type, time_pick):
    fig = pl.plot_grouped(
        df,
        plot_type.value,
        samples=chosen.value or None,
        facet=facet.value,
        err=err.value,
        time=time_pick.value if time_pick is not None else None,
        n_wells=plate.value,
    )
    fig
    return


if __name__ == "__main__":
    app.run()

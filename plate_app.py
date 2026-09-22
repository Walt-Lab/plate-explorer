import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import platelib as pl

    return alt, mo, pl


@app.cell
def _(mo):
    # Holds the well groups you build on the plate: {name: {"wells": [...], "color": "#RRGGBB"}}
    get_groups, set_groups = mo.state({})
    return get_groups, set_groups


@app.cell
def _(mo):
    _files = sorted(
        f.name
        for f in (mo.notebook_dir() / "data").glob("*")
        if f.suffix.lower() in {".csv", ".xlsx", ".xls"}
    )
    source = mo.ui.dropdown(_files, value=_files[0] if _files else None, label="Data file (from the data/ folder)")
    fmt = mo.ui.dropdown(["spectra", "long", "wide", "matrix"], value="spectra", label="Data format")
    plate = mo.ui.dropdown({"96-well": 96, "384-well": 384}, value="384-well", label="Plate")
    enable_groups = mo.ui.checkbox(label="Enable grouping")
    mo.vstack([mo.md("# Plate explorer"), source, mo.hstack([fmt, plate, enable_groups], justify="start")])
    return enable_groups, fmt, plate, source


@app.cell
def _(mo, pl, source):
    _path = str(mo.notebook_dir() / "data" / source.value) if source.value else ""
    _sheets = pl.excel_sheet_names(_path) if _path else [""]
    sheet = mo.ui.dropdown(_sheets, value=_sheets[0], label="Excel sheet")
    sheet
    return (sheet,)


@app.cell
def _(fmt, mo, pl, plate, sheet, source):
    # `data` = raw import: a normal pandas DataFrame you can use in any new cell.
    _path = str(mo.notebook_dir() / "data" / source.value) if source.value else ""
    _kw = {"sheet_name": sheet.value} if sheet.value else {}
    data = pl.load_data(_path, fmt=fmt.value, **_kw) if _path else None
    return (data,)


@app.cell
def _(enable_groups, get_groups, mo, pl):
    # Name/colour boxes for the next group; they advance automatically after each "Add".
    _n = len(get_groups())
    _colors = list(pl.PALETTE)
    group_name = mo.ui.text(value=f"Group {_n + 1}", label="Group name")
    group_color = mo.ui.dropdown(pl.PALETTE, value=_colors[_n % len(_colors)], label="Color")
    group_wells = mo.ui.text(value="", label="Wells (e.g. A1-A5)")
    if enable_groups.value:
        mo.hstack([group_name, group_wells, group_color], justify="start")
    return group_color, group_name, group_wells


@app.cell
def _(alt, enable_groups, get_groups, mo, pl, plate):
    # The virtual plate. Click or drag over wells to select them. Coloured = already in a group.
    _groups = get_groups()
    _table = pl.plate_table(plate.value, _groups).copy()
    _table["col"] = _table["col"].astype(int) + 1
    _table["row"] = _table["row"].astype(int) + 1
    _table["row_label"] = [chr(64 + int(r)) for r in _table["row"]]
    _nr, _nc = pl.plate_shape(plate.value)
    _cell = 34 if _nr <= 8 else 26
    _size = 700 if _nr <= 8 else 400
    _domain = ["(unassigned)"] + list(_groups)
    _range = ["#e6e6e6"] + [g["color"] for g in _groups.values()]
    _selection = alt.selection_point(fields=["well"], empty="all")
    _chart = (
        alt.Chart(_table)
        .mark_circle(size=_size, stroke="#888", strokeWidth=0.5)
        .encode(
            x=alt.X(
                "col:Q",
                title=None,
                scale=alt.Scale(domain=[0.5, _nc + 0.5], nice=False, zero=False),
                axis=alt.Axis(values=list(range(1, _nc + 1)), orient="top", grid=False, ticks=False),
            ),
            y=alt.Y(
                "row_label:N",
                title=None,
                sort=list(chr(65 + i) for i in range(_nr)),
                scale=alt.Scale(domain=list(chr(65 + i) for i in range(_nr)), nice=False),
                axis=alt.Axis(grid=False, ticks=False),
            ),
            color=alt.condition(
                _selection,
                alt.Color("group:N", scale=alt.Scale(domain=_domain, range=_range), legend=alt.Legend(title="Groups")),
                alt.value("#e6e6e6"),
            ),
            strokeWidth=alt.condition(_selection, alt.value(2), alt.value(0.5)),
            tooltip=["well", "group"],
        )
        .add_params(_selection)
        .properties(width=_nc * _cell, height=_nr * _cell)
    )
    picker = mo.ui.altair_chart(_chart, chart_selection="point", legend_selection=False)
    picker if enable_groups.value else mo.md("")
    return (picker,)


@app.cell
def _(enable_groups, get_groups, group_color, group_name, group_wells, mo, pl, picker, plate, set_groups):
    _sel = picker.value
    _wells = []

    if _sel is None:
        _wells = []
    elif hasattr(_sel, "to_dict") and hasattr(_sel, "empty"):
        _records = _sel.to_dict("records") if not _sel.empty else []
        _wells = [row.get("well") for row in _records if row.get("well") is not None]
    elif isinstance(_sel, dict):
        _wells = _sel.get("well", []) if isinstance(_sel.get("well", []), list) else [_sel.get("well")]
        _wells = [w for w in _wells if w is not None]
    elif isinstance(_sel, list):
        _wells = [r["well"] for r in _sel if isinstance(r, dict) and "well" in r]

    _wells = list(dict.fromkeys(_wells))
    if len(_wells) == len(pl.all_wells(plate.value)):
        _wells = []

    _well_error = ""
    if group_wells.value.strip():
        try:
            _wells = pl.expand_wells(group_wells.value, plate.value)
        except ValueError as exc:
            _wells = []
            _well_error = str(exc)

    def _add(_):
        _name = group_name.value.strip()
        if _wells and _name:
            set_groups(lambda g: pl.assign_wells(g, _name, _wells, group_color.value))

    _add_button = mo.ui.button(label="Add selected wells to group", kind="success", on_click=_add)
    _clear_button = mo.ui.button(label="Clear all groups", on_click=lambda v: set_groups({}))

    _rows = []
    for _gname, _g in get_groups().items():
        _rm = mo.ui.button(label="Remove", on_click=lambda v, n=_gname: set_groups(lambda g: pl.remove_group(g, n)))
        _rows.append(
            mo.hstack(
                [mo.md(f"<span style='color:{_g['color']}'>&#9679;</span> **{_gname}**, {len(_g['wells'])} wells"), _rm],
                justify="start",
                align="center",
            )
        )

    if enable_groups.value:
        _group_ui = mo.vstack(
            [
                mo.md(f"**Invalid wells:** {_well_error}") if _well_error else mo.md(""),
                mo.hstack([group_name, group_wells, group_color, _add_button], justify="start", align="end"),
                *_rows,
                _clear_button,
            ]
        )
    else:
        _group_ui = mo.md("")

    _group_ui
    return


@app.cell
def _(data, enable_groups, get_groups, mo, pl, plate):
    # `layout` = well -> sample map built from your groups, `df` = data joined to it.
    if enable_groups.value:
        mo.stop(not get_groups(), mo.md(""))
        layout = pl.layout_from_groups(get_groups(), plate.value)
    else:
        layout = pl.layout_from_groups(
            {"All wells": {"wells": pl.all_wells(plate.value)}}, plate.value
        )
    df = pl.attach_layout(data, layout)
    mo.stop(df.empty, mo.md("None of the selected wells appear in this data file."))
    return df, layout


@app.cell
def _(df, mo):
    return


@app.cell
def _(df, mo, pl):
    plot_type = mo.ui.dropdown(["curves", "heatmap"], value="curves", label="Plot type")
    plot_type
    return (plot_type,)


@app.cell
def _(df, fmt, get_groups, pl, plate, plot_type):
    _colors = {name: g["color"] for name, g in get_groups().items()}
    if not _colors:
        _colors = {"All wells": pl.PALETTE[0]}
    fig = pl.plot_grouped(
        df,
        plot_type.value,
        samples=None,
        facet=False,
        err=None,
        time=None,
        n_wells=plate.value,
        xlabel="wavelength (nm)" if fmt.value == "spectra" else "time",
        colors=_colors,
    )
    fig
    return (fig,)


if __name__ == "__main__":
    app.run()

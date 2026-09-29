import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import io

    import altair as alt
    import marimo as mo
    import platelib as pl

    return alt, io, mo, pl


# ---------------------------------------------------------------------------
# Page switcher. The three "apps" below are shown one at a time: only the cells
# in the "Pages" section at the bottom draw anything, and each one checks which button
# is selected here. Everything else in the file just builds pieces and draws nothing.
# ---------------------------------------------------------------------------
@app.cell
def _(mo):
    HOME = "Home page"
    GROUPING = "Grouping-based spectra"
    MAPNOTES = "Grouping map & notes"
    nav = mo.ui.tabs({HOME: mo.md(""), GROUPING: mo.md(""), MAPNOTES: mo.md("")})
    mo.vstack([mo.md("# Plate explorer"), nav])
    return GROUPING, HOME, MAPNOTES, nav


@app.cell
def _(GROUPING, HOME, MAPNOTES, nav):
    # Name of the page whose button is selected (falls back to the Home page).
    page = nav.value if nav.value in (HOME, GROUPING, MAPNOTES) else HOME
    return (page,)


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
    upload = mo.ui.file(filetypes=[".csv", ".xlsx", ".xls"], label="...or upload a file")
    fmt = mo.ui.dropdown(["spectra", "long", "wide", "matrix"], value="spectra", label="Data format")
    plate = mo.ui.dropdown({"96-well": 96, "384-well": 384}, value="384-well", label="Plate")
    home_controls = mo.vstack(
        [
            mo.hstack([source, upload], justify="start"),
            mo.hstack([fmt, plate], justify="start"),
        ]
    )
    return fmt, home_controls, plate, source, upload


@app.cell
def _(mo, pl, source, upload):
    if upload.value:
        _up = upload.value[0]
        _path = pl.to_readable(_up.name, _up.contents)
    else:
        _path = str(mo.notebook_dir() / "data" / source.value) if source.value else ""
    _sheets = pl.excel_sheet_names(_path) if _path else [""]
    sheet = mo.ui.dropdown(_sheets, value=_sheets[0], label="Excel sheet")
    sheet_view = mo.hstack([sheet], justify="start")
    return sheet, sheet_view


@app.cell
def _(fmt, mo, pl, sheet, source, upload):
    # `data` = raw import: a normal pandas DataFrame you can use in any new cell.
    if upload.value:
        _up = upload.value[0]
        _src = pl.to_readable(_up.name, _up.contents)
    else:
        _src = str(mo.notebook_dir() / "data" / source.value) if source.value else ""
    _kw = {"sheet_name": sheet.value} if sheet.value else {}
    try:
        data = pl.load_data(_src, fmt=fmt.value, **_kw) if _src else None
        data_error = ""
    except Exception as exc:  # show the problem on the Home page instead of blanking every page
        data = None
        data_error = str(exc)
    return data, data_error


@app.cell
def _(get_groups, mo, pl):
    # Name/colour boxes for the next group; they advance automatically after each "Add".
    _n = len(get_groups())
    _names = list(pl.COLOR_CHOICES)
    group_name = mo.ui.text(value=f"Group {_n + 1}", label="Group name")
    group_color = mo.ui.dropdown(pl.COLOR_CHOICES, value=_names[_n % len(_names)], label="Color")
    group_wells = mo.ui.text(value="", label="Wells (e.g. A1-A5)")
    return group_color, group_name, group_wells


@app.cell
def _(alt, data, get_groups, mo, pl, plate):
    # The virtual plate. Click or drag over wells to select them.
    # Fill color = each well's signal (heatmap, from the loaded data).
    # Ring color = group assignment. Dimmed = not currently selected.
    _groups = get_groups()
    _table = pl.plate_table(plate.value, _groups).copy()
    _table["col"] = _table["col"].astype(int) + 1
    _table["row"] = _table["row"].astype(int) + 1
    _table["row_label"] = [chr(64 + int(r)) for r in _table["row"]]

    if data is not None and not data.empty:
        _times = data["time"].dropna()
        _endpoint = data[data["time"] == _times.max()] if not _times.empty else data
        _vals = _endpoint.groupby("well", as_index=False)["value"].mean()
        _table = _table.merge(_vals, on="well", how="left")
    else:
        _table["value"] = float("nan")

    _nr, _nc = pl.plate_shape(plate.value)
    _cell = 34 if _nr <= 8 else 26
    _size = 700 if _nr <= 8 else 400
    _domain = ["(unassigned)"] + list(_groups)
    _range = ["#bbbbbb"] + [g["color"] for g in _groups.values()]
    _selection = alt.selection_point(fields=["well"], empty="all")
    _chart = (
        alt.Chart(_table)
        .mark_circle(size=_size)
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
            color=alt.Color(
                "value:Q",
                title="Signal",
                scale=alt.Scale(scheme="viridis"),
                legend=alt.Legend(title="Signal"),
            ),
            stroke=alt.Stroke(
                "group:N",
                scale=alt.Scale(domain=_domain, range=_range),
                legend=alt.Legend(title="Group"),
            ),
            strokeWidth=alt.condition(_selection, alt.value(3), alt.value(1)),
            opacity=alt.condition(_selection, alt.value(1.0), alt.value(0.35)),
            tooltip=["well", "group", "value"],
        )
        .add_params(_selection)
        .properties(width=_nc * _cell, height=_nr * _cell)
    )
    picker = mo.ui.altair_chart(_chart, chart_selection="point", legend_selection=False)
    # Pages show this wrapper, not `picker` itself, so picking wells doesn't redraw the plate.
    picker_view = mo.vstack([picker])
    return picker, picker_view


@app.cell
def _(get_groups, group_color, group_name, group_wells, mo, pl, picker, plate, set_groups):
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

    group_ui = mo.vstack(
        [
            mo.md(f"**Invalid wells:** {_well_error}") if _well_error else mo.md(""),
            mo.hstack([group_name, group_wells, group_color, _add_button], justify="start", align="end"),
            *_rows,
            _clear_button,
        ]
    )
    return (group_ui,)


@app.cell
def _(data, get_groups, pl, plate):
    # `layout` = well -> sample map built from your groups (or every well as one sample
    # if you haven't made groups), `df` = data joined to it.
    import pandas as _pd

    _groups = get_groups()
    if _groups:
        layout = pl.layout_from_groups(_groups, plate.value)
    else:
        layout = pl.layout_from_groups({"All wells": {"wells": pl.all_wells(plate.value)}}, plate.value)
    try:
        df = pl.attach_layout(data, layout) if data is not None else _pd.DataFrame()
    except Exception:
        df = _pd.DataFrame()
    return df, layout


@app.cell
def _(mo):
    plot_type = mo.ui.dropdown(["curves", "heatmap"], value="curves", label="Plot type")
    plot_type_view = mo.hstack([plot_type], justify="start")
    return plot_type, plot_type_view


@app.cell
def _(data, data_error, df, fmt, get_groups, mo, pl, plate, plot_type):
    fig = None
    if data_error:
        home_plot = mo.md(f"**Couldn't read that file:** {data_error}")
    elif data is None:
        home_plot = mo.md("Choose a data file (or upload one) to see the plot.")
    elif df.empty:
        home_plot = mo.md("None of the selected wells appear in this data file.")
    else:
        _colors = {name: g["color"] for name, g in get_groups().items()}
        if not _colors:
            _colors = {"All wells": pl.PALETTE[0]}
        try:
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
            home_plot = fig
        except Exception as exc:
            home_plot = mo.md(f"**Couldn't draw the plot:** {exc}")
    return fig, home_plot


# ---------------------------------------------------------------------------
# Grouping map & notes: a separate virtual plate for planning/documenting which
# samples are in which wells. It uses NO data and does not touch the groups above.
# The group name is the label. Notes are optional and can be typed when the group is
# created, or added/changed later by clicking any well of the group.
# ---------------------------------------------------------------------------
@app.cell
def _(mo):
    # {name: {"wells": [...], "color": "#RRGGBB"}}
    get_map, set_map = mo.state({}, allow_self_loops=True)
    return get_map, set_map


@app.cell
def _():
    # {group name: notes text}. A plain dict on purpose: typing a note never redraws the
    # plate or the forms, so nothing you typed can be wiped out when something else changes.
    notes_store = {}
    # Scratch space shared between cells (also a plain dict, so writing to it redraws nothing):
    #   "wells": wells the next "Add" will use   "error": problem with typed wells, if any
    #   "boxes": the notes box currently open for the clicked group
    pending = {"wells": [], "error": "", "boxes": {}}
    return notes_store, pending


@app.cell
def _(mo):
    get_msg, set_msg = mo.state("", allow_self_loops=True)  # feedback line next to the Add button
    return get_msg, set_msg


@app.cell
def _(alt, get_map, mo, notes_store, pl, plate):
    # The grouping map: same plate layout and click/drag selection as the plot picker,
    # but each well is filled with its group color (no signal values).
    # Hover over a well to see its group and that group's notes.
    _groups = get_map()
    _table = pl.plate_table(plate.value, _groups).copy()
    _table["col"] = _table["col"].astype(int) + 1
    _table["row"] = _table["row"].astype(int) + 1
    _table["row_label"] = [chr(64 + int(r)) for r in _table["row"]]
    _table["notes"] = _table["group"].map({k: notes_store.get(k, "") for k in _groups}).fillna("")

    _nr, _nc = pl.plate_shape(plate.value)
    _cell = 34 if _nr <= 8 else 26
    _size = 700 if _nr <= 8 else 400
    _domain = ["(unassigned)"] + list(_groups)
    _range = ["#eeeeee"] + [g["color"] for g in _groups.values()]
    _selection = alt.selection_point(fields=["well"], empty="all")
    _chart = (
        alt.Chart(_table)
        .mark_circle(size=_size, stroke="#888888")
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
            color=alt.Color(
                "group:N",
                scale=alt.Scale(domain=_domain, range=_range),
                legend=alt.Legend(title="Group"),
            ),
            strokeWidth=alt.condition(_selection, alt.value(3), alt.value(1)),
            opacity=alt.condition(_selection, alt.value(1.0), alt.value(0.35)),
            tooltip=["well", "group", alt.Tooltip("notes:N", title="Notes")],
        )
        .add_params(_selection)
        .properties(width=_nc * _cell, height=_nr * _cell)
    )
    map_picker = mo.ui.altair_chart(_chart, chart_selection="point", legend_selection=False)
    # Pages show this wrapper, not `map_picker` itself, so clicking wells doesn't redraw the plate.
    map_picker_view = mo.vstack([map_picker])
    return map_picker, map_picker_view


@app.cell
def _(map_picker, pl, plate):
    # Wells currently selected on the map by clicking/dragging (empty if nothing is selected).
    _sel = map_picker.value
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
    # "Everything selected" just means nothing is selected.
    if len(_wells) == len(pl.all_wells(plate.value)):
        _wells = []
    map_selected = _wells
    return (map_selected,)


@app.cell
def _(get_map, map_selected):
    # The group you clicked on: set only when every selected well belongs to the same group.
    _groups = get_map()
    _owners = {next((n for n, g in _groups.items() if w in g["wells"]), None) for w in map_selected}
    active_group = next(iter(_owners)) if len(_owners) == 1 and None not in _owners else None
    return (active_group,)


@app.cell
def _(active_group, get_map, mo, notes_store, pending, set_map, set_msg):
    # Click a group on the map -> a box opens here with that group's notes, ready to edit.
    # Notes also save themselves when you click out of the box.
    import html as _html

    pending["boxes"] = {}
    _g = get_map().get(active_group) if active_group else None
    if _g is not None:
        _name = active_group
        _box = mo.ui.text_area(
            value=notes_store.get(_name, ""),
            rows=5,
            full_width=True,
            label="Notes",
            placeholder="Type notes for this group...",
            on_change=lambda v: notes_store.__setitem__(_name, (v or "").strip()),
        )
        pending["boxes"] = {_name: _box}  # lets the Add button save this box too

        def _save(_):
            notes_store[_name] = (_box.value or "").strip()
            set_msg(f"Saved notes for \u201c{_name}\u201d \u2713")
            set_map(lambda g: dict(g))  # redraw so the hover text on the plate is up to date

        _save_btn = mo.ui.button(label="Save notes", kind="success", on_click=_save)
        _head = mo.Html(
            f"<span style='color:{_g['color']}'>&#9679;</span> <b>{_html.escape(_name)}</b>"
            f" &nbsp;&middot;&nbsp; {len(_g['wells'])} wells"
        )
        _panel = mo.callout(mo.vstack([_head, _box, _save_btn]), kind="neutral")
    else:
        _panel = mo.md("")
    notes_panel = _panel
    return (notes_panel,)


@app.cell
def _(get_map, mo, pl):
    # The form for the next group: name, wells, color, notes. It is rebuilt (so it comes back
    # empty, with the next default name/color) every time a group is added or removed.
    _n = len(get_map())
    _names = list(pl.COLOR_CHOICES)
    map_name = mo.ui.text(value=f"Group {_n + 1}", label="Group name")
    map_color = mo.ui.dropdown(pl.COLOR_CHOICES, value=_names[_n % len(_names)], label="Color")
    map_wells = mo.ui.text(value="", label="Wells (e.g. A1-A5)")
    map_notes = mo.ui.text_area(value="", label="Notes", rows=3, full_width=True)
    # The Add button reads these through this dict, so typing in a box never rebuilds the button.
    map_inputs = {"name": map_name, "color": map_color, "notes": map_notes}
    map_form = mo.vstack(
        [
            mo.hstack([map_name, map_wells, map_color], justify="start", align="end"),
            map_notes,
        ]
    )
    return map_color, map_form, map_inputs, map_name, map_notes, map_wells


@app.cell
def _(map_selected, map_wells, mo, pending, pl, plate):
    # Live hint under the notes box. Also works out which wells the Add button will use:
    # a range typed in "Wells" wins, otherwise whatever is selected on the plate.
    _wells = list(map_selected)
    _err = ""
    if map_wells.value.strip():
        try:
            _wells = pl.expand_wells(map_wells.value, plate.value)
        except ValueError as exc:
            _wells = []
            _err = str(exc)
    pending["wells"] = _wells
    pending["error"] = _err

    if _err:
        _hint = mo.md(f"**Invalid wells:** {_err}")
    elif _wells:
        _hint = mo.md(f"**{len(_wells)} wells** ready to add. Press the green button to put them in a group.")
    else:
        _hint = mo.md("")
    map_hint = _hint
    return (map_hint,)


@app.cell
def _(get_map, get_msg, map_inputs, mo, notes_store, pending, pl, set_map, set_msg):
    # The Add button (bottom of the form) and the list of groups made so far.
    import html as _html

    _groups_now = get_map()

    def _add(_):
        _name = map_inputs["name"].value.strip()
        _note = map_inputs["notes"].value.strip()
        _color = map_inputs["color"].value
        _wells = list(pending["wells"])
        if pending["error"]:
            set_msg(f"Couldn't add: {pending['error']}")
            return
        if not _name:
            set_msg("Give the group a name first.")
            return
        try:
            if _wells:
                # Save everything: notes from the open notes box (if any), then the new group.
                for _n, _b in pending["boxes"].items():
                    if _n in _groups_now:
                        notes_store[_n] = (_b.value or "").strip()
                if _note:  # a blank box keeps any notes the group already has
                    notes_store[_name] = _note
                set_map(lambda g: pl.assign_wells(g, _name, _wells, _color))
                set_msg(f"Added {len(_wells)} wells to \u201c{_name}\u201d \u2713")
            elif _note and _name in _groups_now:
                # No wells chosen: just save the notes onto the existing group with this name.
                notes_store[_name] = _note
                set_map(lambda g: dict(g))
                set_msg(f"Saved notes for \u201c{_name}\u201d \u2713")
            else:
                set_msg("Pick some wells first: click or drag on the plate, or type a range like A1-A5.")
        except Exception as exc:  # show the problem instead of failing silently
            set_msg(f"Couldn't add: {exc}")

    _add_button = mo.ui.button(label="Add selected wells to group", kind="success", on_click=_add)
    _clear_button = mo.ui.button(
        label="Clear all groups",
        on_click=lambda v: (notes_store.clear(), set_msg(""), set_map({})),
    )

    _rows = []
    for _gname, _g in _groups_now.items():
        _rm = mo.ui.button(
            label="Remove",
            on_click=lambda v, n=_gname: (notes_store.pop(n, None), set_map(lambda g: pl.remove_group(g, n))),
        )
        _note_txt = notes_store.get(_gname, "")
        # Hovering over the group name shows its notes (browser tooltip).
        _label = (
            f"<span title=\"{_html.escape(_note_txt, quote=True)}\">"
            f"<span style='color:{_g['color']}'>&#9679;</span> <b>{_html.escape(_gname)}</b>, "
            f"{len(_g['wells'])} wells{' &#128221;' if _note_txt else ''}</span>"
        )
        _rows.append(mo.hstack([mo.md(_label), _rm], justify="start", align="center"))

    map_actions = mo.vstack(
        [
            mo.hstack([_add_button, mo.md(get_msg())], justify="start", align="center"),
            *_rows,
            _clear_button if _rows else mo.md(""),
        ]
    )
    return (map_actions,)


# ---------------------------------------------------------------------------
# Pages: each cell below shows one piece, and only while its button is selected above.
# They only read the finished pieces (never the raw inputs), so using a page never
# redraws it out from under you.
# ---------------------------------------------------------------------------
@app.cell
def _(HOME, home_controls, mo, page):
    home_controls if page == HOME else mo.md("")
    return


@app.cell
def _(HOME, mo, page, sheet_view):
    sheet_view if page == HOME else mo.md("")
    return


@app.cell
def _(HOME, mo, page, plot_type_view):
    plot_type_view if page == HOME else mo.md("")
    return


@app.cell
def _(HOME, home_plot, mo, page):
    home_plot if page == HOME else mo.md("")
    return


@app.cell
def _(GROUPING, mo, page, picker_view):
    picker_view if page == GROUPING else mo.md("")
    return


@app.cell
def _(GROUPING, group_ui, mo, page):
    group_ui if page == GROUPING else mo.md("")
    return


@app.cell
def _(MAPNOTES, map_picker_view, mo, page):
    map_picker_view if page == MAPNOTES else mo.md("")
    return


@app.cell
def _(MAPNOTES, mo, notes_panel, page):
    notes_panel if page == MAPNOTES else mo.md("")
    return


@app.cell
def _(MAPNOTES, map_form, mo, page):
    map_form if page == MAPNOTES else mo.md("")
    return


@app.cell
def _(MAPNOTES, map_hint, mo, page):
    map_hint if page == MAPNOTES else mo.md("")
    return


@app.cell
def _(MAPNOTES, map_actions, mo, page):
    map_actions if page == MAPNOTES else mo.md("")
    return


if __name__ == "__main__":
    app.run()

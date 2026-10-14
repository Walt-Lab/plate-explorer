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
    HOME = "Data overview"
    GROUPING = "Grouping-based spectra"
    MAPNOTES = "Grouping map & notes"
    nav = mo.ui.tabs({HOME: mo.md(""), MAPNOTES: mo.md(""), GROUPING: mo.md("")})
    mo.vstack([mo.md("# Plate explorer"), nav])
    return GROUPING, HOME, MAPNOTES, nav


@app.cell
def _(GROUPING, HOME, MAPNOTES, nav):
    # Name of the page whose button is selected (falls back to the first tab).
    page = nav.value if nav.value in (HOME, GROUPING, MAPNOTES) else HOME
    return (page,)


@app.cell
def _(mo):
    # Holds the well groups you build on the plate: {name: {"wells": [...], "color": "#RRGGBB"}}
    get_groups, set_groups = mo.state({})
    return get_groups, set_groups


@app.cell
def _(mo):
    upload = mo.ui.file(
        filetypes=[".csv", ".xlsx", ".xls"],
        label="Upload data file",
    )
    home_plate = mo.ui.dropdown({"96-well": 96, "384-well": 384}, value="384-well", label="Plate")
    group_plate = mo.ui.dropdown({"96-well": 96, "384-well": 384}, value="384-well", label="Plate")
    return group_plate, home_plate, upload


@app.cell
def _(mo, pl, upload):
    _uploaded_file = upload.value[0] if upload.value else None

    def resolve_file():
        if _uploaded_file:
            return pl.to_readable(
                _uploaded_file.name,
                _uploaded_file.contents,
            )
        return ""

    file_name = _uploaded_file.name if _uploaded_file else "None selected"
    return file_name, resolve_file


@app.cell
def _(home_plate, mo, upload, file_name):
    data_file_label = mo.md(f"**Data file:** {file_name}")
    home_controls = mo.hstack(
        [upload, home_plate, data_file_label],
        justify="start",
        align="center",
        wrap=True,
    )
    group_file_label = mo.md(f"**Data file:** {file_name}")
    return group_file_label, home_controls


@app.cell
def _(mo, pl, resolve_file):
    home_path = resolve_file()

    _sheet_names = []
    _overview_rows = []
    for _sheet_name in pl.excel_sheet_names(home_path) if home_path else []:
        _names = pl.tecan_measurement_names(home_path, sheet_name=_sheet_name)
        if not _names:
            continue
        _sheet_names.append(_sheet_name)
        _types = {
            "Kinetics": [name for name in _names if name == "Kinetic measurement"],
            "Absorbance": [name for name in _names if "absorb" in name.lower()],
            "Emission": [name for name in _names if "emission" in name.lower()],
            "Wavelength scan": [
                name
                for name in _names
                if name.startswith("Wavelength scan —")
                and "absorb" not in name.lower()
                and "emission" not in name.lower()
            ],
            "Plate scan": [name for name in _names if name.startswith("Plate scan —")],
        }
        _summary = [
            f"{kind} ({', '.join(name.split(' — ', 1)[-1] for name in names)})"
            for kind, names in _types.items()
            if names
        ]
        _overview_rows.append((_sheet_name or "Uploaded data", ", ".join(_summary)))

    home_sheet = mo.ui.dropdown(
        _sheet_names,
        value=_sheet_names[0] if _sheet_names else None,
        label="Sheet",
    )

    if _overview_rows:
        _contents = "\n".join(
            f"- **{sheet_name}:** {data_types}"
            for sheet_name, data_types in _overview_rows
        )
        workbook_summary = mo.md(f"**Workbook contents**\n\n{_contents}")
    elif home_path:
        workbook_summary = mo.md("**Workbook contents**\n\nNo supported measurements found.")
    else:
        workbook_summary = mo.md("")
    return home_path, home_sheet, workbook_summary


@app.cell
def _(mo, pl, resolve_file):
    group_path = resolve_file()

    _sheet_names = []
    _overview_rows = []
    for _sheet_name in pl.excel_sheet_names(group_path) if group_path else []:
        _names = pl.tecan_measurement_names(group_path, sheet_name=_sheet_name)
        if not _names:
            continue
        _sheet_names.append(_sheet_name)
        _types = {
            "Kinetics": [name for name in _names if name == "Kinetic measurement"],
            "Absorbance": [name for name in _names if "absorb" in name.lower()],
            "Emission": [name for name in _names if "emission" in name.lower()],
            "Wavelength scan": [
                name
                for name in _names
                if name.startswith("Wavelength scan —")
                and "absorb" not in name.lower()
                and "emission" not in name.lower()
            ],
            "Plate scan": [name for name in _names if name.startswith("Plate scan —")],
        }
        _summary = [
            f"{kind} ({', '.join(name.split(' — ', 1)[-1] for name in names)})"
            for kind, names in _types.items()
            if names
        ]
        _overview_rows.append((_sheet_name or "Uploaded data", ", ".join(_summary)))
    group_sheet = mo.ui.dropdown(
        _sheet_names,
        value=_sheet_names[0] if _sheet_names else None,
        label="Sheet",
    )
    if _overview_rows:
        _contents = "\n".join(
            f"- **{sheet_name}:** {data_types}"
            for sheet_name, data_types in _overview_rows
        )
        group_workbook_summary = mo.md(f"**Workbook contents**\n\n{_contents}")
    elif group_path:
        group_workbook_summary = mo.md("**Workbook contents**\n\nNo supported measurements found.")
    else:
        group_workbook_summary = mo.md("")
    return group_path, group_sheet, group_workbook_summary


@app.cell
def _(group_path, group_sheet, home_path, home_sheet, mo, pl):
    def _make_data_selector(path, sheet):
        _names = pl.tecan_measurement_names(path, sheet_name=sheet.value) if path and sheet.value else []
        _options = {}
        for _name in _names:
            if _name == "Kinetic measurement":
                _kind = "Kinetics"
            elif "absorb" in _name.lower():
                _kind = "Absorbance"
            elif "emission" in _name.lower():
                _kind = "Emission"
            elif _name.startswith("Plate scan —"):
                _kind = "Plate scan"
            elif _name.startswith("Wavelength scan —"):
                _kind = "Wavelength scan"
            else:
                _kind = "Data"
            _display_name = _name.split(" — ", 1)[-1]
            _options[f"{_kind} — {_display_name}"] = _name
        return mo.ui.dropdown(
            _options,
            value=next(iter(_options), None),
            label="Data",
        )

    home_data_choice = _make_data_selector(home_path, home_sheet)
    group_data_choice = _make_data_selector(group_path, group_sheet)
    return group_data_choice, home_data_choice


@app.cell
def _(group_data_choice, group_path, group_sheet, home_data_choice, home_path, home_sheet, mo, pl):
    def _load_selected(path, sheet, selected_data):
        _src = path
        if not _src or not sheet.value:
            return None, "", "time (s)"
        if not selected_data.value:
            return None, "No supported data was found on the selected sheet.", "time (s)"
        try:
            _loaded = pl.load_data(
                _src,
                fmt="tecan",
                sheet_name=sheet.value,
                measurement=selected_data.value,
            )
            return _loaded, "", _loaded.attrs.get("x_label", "time (s)")
        except Exception as exc:
            return None, str(exc), "time"

    home_data, home_data_error, home_axis_label = _load_selected(home_path, home_sheet, home_data_choice)
    group_data, group_data_error, group_axis_label = _load_selected(group_path, group_sheet, group_data_choice)
    return (
        group_axis_label,
        group_data,
        group_data_error,
        home_axis_label,
        home_data,
        home_data_error,
    )


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
def _(pl):
    def groups_matching_note_keywords(groups, map_groups, notes, query):
        keywords = []
        seen_keywords = set()
        for keyword in query.replace(";", ",").split(","):
            keyword = keyword.strip()
            folded = keyword.casefold()
            if keyword and folded not in seen_keywords:
                keywords.append(keyword)
                seen_keywords.add(folded)
        result = {
            name: {**info, "wells": list(info.get("wells", []))}
            for name, info in groups.items()
        }
        keyword_wells = set()
        matched_keywords = []
        for keyword in keywords:
            _folded_keyword = keyword.casefold()
            _matches = [
                (name, info)
                for name, info in map_groups.items()
                if _folded_keyword in (notes.get(name) or "").casefold()
            ]
            if not _matches:
                continue

            matched_keywords.append(keyword)
            wells = {
                well
                for _, info in _matches
                for well in info.get("wells", [])
            }
            keyword_wells.update(wells)
            _existing = result.get(keyword, {})
            _color = _existing.get("color") or _matches[0][1].get("color")
            result[keyword] = {
                **_existing,
                "wells": sorted(
                    set(_existing.get("wells", [])) | wells,
                    key=pl.parse_well,
                ),
                "color": _color,
            }
        return result, matched_keywords, keyword_wells

    return (groups_matching_note_keywords,)


@app.cell
def _(alt, group_data, group_keyword_wells, group_plate, mo, plot_groups, pl):
    # The virtual plate. Click or drag over wells to select them.
    # Fill color = each well's signal (heatmap, from the loaded data).
    # Ring color = group assignment. Dimmed = not currently selected.
    _groups = plot_groups
    _table = pl.plate_table(group_plate.value, _groups).copy()
    _table["keyword_match"] = _table["well"].isin(group_keyword_wells)
    _table["stroke_group"] = _table.apply(
        lambda row: "Keyword match" if row["keyword_match"] else row["group"],
        axis=1,
    )
    _table["keyword_stroke_width"] = _table["keyword_match"].map(
        {True: 4, False: 1}
    )
    _table["col"] = _table["col"].astype(int) + 1
    _table["row"] = _table["row"].astype(int) + 1
    _table["row_label"] = [chr(64 + int(r)) for r in _table["row"]]

    if group_data is not None and not group_data.empty:
        _times = group_data["time"].dropna()
        _endpoint = group_data[group_data["time"] == _times.max()] if not _times.empty else group_data
        _vals = _endpoint.groupby("well", as_index=False)["value"].mean()
        _table = _table.merge(_vals, on="well", how="left")
    else:
        _table["value"] = float("nan")

    _nr, _nc = pl.plate_shape(group_plate.value)
    _cell = 34 if _nr <= 8 else 26
    _size = 700 if _nr <= 8 else 400
    _stroke_colors = dict(zip(_table["group"], _table["group_color"]))
    _stroke_colors["Keyword match"] = "#ffd54f"
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
                "stroke_group:N",
                scale=alt.Scale(
                    domain=list(_stroke_colors),
                    range=list(_stroke_colors.values()),
                ),
                legend=alt.Legend(title="Group"),
            ),
            strokeWidth=alt.StrokeWidth(
                "keyword_stroke_width:Q", scale=None, legend=None
            ),
            opacity=alt.condition(_selection, alt.value(1.0), alt.value(0.35)),
            tooltip=["well", "group", "value", "keyword_match"],
        )
        .add_params(_selection)
        .properties(width=_nc * _cell, height=_nr * _cell)
    )
    picker = mo.ui.altair_chart(_chart, chart_selection="point", legend_selection=False)
    # Pages show this wrapper, not `picker` itself, so picking wells doesn't redraw the plate.
    picker_view = mo.vstack([picker])
    return picker, picker_view


@app.cell
def _(get_groups, group_color, group_name, group_wells, group_plate, mo, pl, picker, set_groups):
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
    if len(_wells) == len(pl.all_wells(group_plate.value)):
        _wells = []

    _well_error = ""
    if group_wells.value.strip():
        try:
            _wells = pl.expand_wells(group_wells.value, group_plate.value)
        except ValueError as exc:
            _wells = []
            _well_error = str(exc)

    def _add(_):
        _name = group_name.value.strip()
        if _wells and _name and _name not in get_groups():
            set_groups(lambda g: pl.assign_wells(g, _name, _wells, group_color.value))

    _add_button = mo.ui.button(label="Create group", kind="success", on_click=_add)
    _clear_button = mo.ui.button(label="Clear all groups", on_click=lambda v: set_groups({}))

    _rows = []
    for _gname, _g in get_groups().items():
        _edit_action = mo.ui.dropdown(
            {"Add selected wells": "add", "Remove selected wells": "remove"},
            value="Add selected wells",
            label="",
        )
        _edit_button = mo.ui.button(
            label="Apply",
            on_click=lambda v, n=_gname, a=_edit_action: (
                set_groups(
                    lambda g: pl.update_group_wells(
                        g, n, _wells, a.value
                    )
                )
                if _wells and not _well_error
                else None
            ),
        )
        _rm = mo.ui.button(
            label="Delete group",
            on_click=lambda v, n=_gname: set_groups(lambda g: pl.remove_group(g, n)),
        )
        _rows.append(
            mo.vstack(
                [
                    mo.hstack(
                        [
                            mo.md(f"<span style='color:{_g['color']}'>&#9679;</span> **{_gname}**, {len(_g['wells'])} wells"),
                            _edit_action,
                            _edit_button,
                        ],
                        justify="start",
                        align="center",
                    ),
                    _rm,
                ],
                align="start",
            )
        )

    group_ui = mo.vstack(
        [
            mo.md(
                "Edit an existing grouping of wells using the Add/Remove controls. "
                "A well can belong to multiple groups."
            )
            if get_groups()
            else mo.md(""),
            mo.md(f"**Invalid wells:** {_well_error}") if _well_error else mo.md(""),
            mo.hstack([group_name, group_wells, group_color, _add_button], justify="start", align="end"),
            *_rows,
            _clear_button,
        ]
    )
    return (group_ui,)


@app.cell
def _(
    get_groups,
    get_map,
    group_data,
    group_note_search,
    group_plate,
    groups_matching_note_keywords,
    home_data,
    home_plate,
    mo,
    notes_store,
    pl,
):
    # Two versions of the data, each joined to a well -> sample layout:
    #   layout_all / df_all : every well as one sample ("All wells")     -> Home page
    #   layout / df         : built from the groups you made             -> Grouping-based spectra
    # (`df` is empty until you've made at least one group.)
    import pandas as _pd

    def _attach(source_data, lay):
        try:
            return pl.attach_layout(source_data, lay) if source_data is not None else _pd.DataFrame()
        except Exception:
            return _pd.DataFrame()

    layout_all = pl.layout_from_groups({"All wells": {"wells": pl.all_wells(home_plate.value)}}, home_plate.value)
    df_all = _attach(home_data, layout_all)
    _matched_groups, _matched_keywords, _keyword_wells = groups_matching_note_keywords(
        {}, get_map(), notes_store, group_note_search.value
    )
    _nr, _nc = pl.plate_shape(group_plate.value)
    _out_of_range = []
    for _name in _matched_keywords:
        _valid_wells = []
        for _well in _matched_groups[_name].get("wells", []):
            _row, _column = pl.parse_well(_well)
            if _row >= _nr or _column >= _nc:
                _out_of_range.append(_well)
            else:
                _valid_wells.append(_well)
        _matched_groups[_name]["wells"] = _valid_wells
    _groups = get_groups()
    if _matched_keywords:
        if _out_of_range:
            _keyword_status = mo.md(
                f"Found map-note match(es) for {', '.join(_matched_keywords)}. "
                f"{len(set(_out_of_range))} well(s) are outside the selected "
                f"{group_plate.value}-well plate and will be skipped when added."
            )
        else:
            _already_added = all(
                name in _groups
                and set(_matched_groups[name].get("wells", [])).issubset(
                    _groups[name].get("wells", [])
                )
                for name in _matched_keywords
            )
            if _already_added:
                _keyword_status = mo.md(
                    f"Keyword group(s) in the graph: {', '.join(_matched_keywords)}."
                )
            else:
                _keyword_status = mo.md(
                    f"Found map-note match(es) for {', '.join(_matched_keywords)}. "
                    "Select **create group by keyword** to add them to the graph."
                )
    elif group_note_search.value.strip():
        _keyword_status = mo.md("No map-group notes match those keywords.")
    else:
        _keyword_status = mo.md("")
    group_keyword_status = _keyword_status
    layout = pl.layout_from_groups(_groups, group_plate.value) if _groups else pl.layout_from_groups(
        {"All wells": {"wells": pl.all_wells(group_plate.value)}},
        group_plate.value,
    )
    df = _attach(group_data, layout) if _groups else _pd.DataFrame()
    plot_groups = _groups
    group_keyword_wells = _keyword_wells - set(_out_of_range)
    return (
        df,
        df_all,
        group_keyword_status,
        group_keyword_wells,
        layout,
        layout_all,
        plot_groups,
    )


@app.cell
def _(
    get_map,
    group_data_choice,
    group_plate,
    group_sheet,
    groups_matching_note_keywords,
    home_data_choice,
    home_plate,
    home_sheet,
    mo,
    notes_store,
    pl,
    set_groups,
):
    _home_plot_default = (
        "heatmap"
        if home_data_choice.value
        and home_data_choice.value.startswith("Plate scan —")
        else "curves"
    )
    plot_type = mo.ui.dropdown(
        ["curves", "heatmap"],
        value=_home_plot_default,
        label="Plot type",
    )
    home_plot_controls = mo.hstack(
        [home_sheet, home_data_choice, plot_type],
        justify="start",
    )
    _group_plot_default = (
        "heatmap"
        if group_data_choice.value
        and group_data_choice.value.startswith("Plate scan —")
        else "curves"
    )
    group_plot_type = mo.ui.dropdown(
        ["curves", "heatmap"],
        value=_group_plot_default,
        label="Plot type",
    )
    group_trace_mode = mo.ui.dropdown(
        {
            "Average": "average",
            "Individual wells": "individual",
            "Average + individual": "both",
        },
        value="Average",
        label="Trace display (curves)",
    )
    group_note_search = mo.ui.text(
        value="",
        label="Add map groups by note keywords",
        placeholder="Enter keywords, separated by commas",
        full_width=True,
    )

    def _add_keyword_groups(_):
        _matched_groups, _matched_keywords, _ = groups_matching_note_keywords(
            {}, get_map(), notes_store, group_note_search.value
        )
        _nr, _nc = pl.plate_shape(group_plate.value)
        _valid_groups = {}
        for _name in _matched_keywords:
            _wells = []
            for _well in _matched_groups[_name].get("wells", []):
                _row, _column = pl.parse_well(_well)
                if _row < _nr and _column < _nc:
                    _wells.append(_well)
            if _wells:
                _valid_groups[_name] = (_wells, _matched_groups[_name].get("color"))
        if _valid_groups:
            def _update_groups(_groups):
                for _name, (_wells, _color) in _valid_groups.items():
                    _color = _groups.get(_name, {}).get("color") or _color
                    _groups = pl.assign_wells(_groups, _name, _wells, _color)
                return _groups

            set_groups(_update_groups)

    group_note_add_button = mo.ui.button(
        label="Create group by keyword",
        kind="success",
        on_click=_add_keyword_groups,
    )
    group_note_controls = mo.vstack([group_note_search, group_note_add_button])
    group_plot_controls = mo.hstack(
        [group_sheet, group_data_choice, group_plot_type, group_trace_mode, group_plate],
        justify="start",
    )
    return (
        group_note_controls,
        group_note_search,
        group_plot_controls,
        group_plot_type,
        group_trace_mode,
        home_plot_controls,
        plot_type,
    )


@app.cell
def _(df_all, home_axis_label, home_data, home_data_error, home_plate, mo, pl, plot_type):
    # Home page plot: the whole plate, no grouping.
    fig = None
    if home_data_error:
        home_plot = mo.md(f"**Couldn't read that file:** {home_data_error}")
    elif home_data is None:
        home_plot = mo.md("Choose a data file (or upload one) to see the plot.")
    elif df_all.empty:
        home_plot = mo.md("None of the wells appear in this data file.")
    else:
        try:
            fig = pl.plot_grouped(
                df_all,
                plot_type.value,
                samples=None,
                facet=False,
                err=None,
                time=None,
                n_wells=home_plate.value,
                xlabel=home_axis_label,
                colors={"All wells": pl.PALETTE[0]},
            )
            home_plot = fig
        except Exception as exc:
            home_plot = mo.md(f"**Couldn't draw the plot:** {exc}")
    return fig, home_plot


@app.cell
def _(df, group_axis_label, group_data, group_data_error, group_plot_type, group_trace_mode, mo, plot_groups, pl):
    # Grouping-based spectra plot: one trace per group you made, in the group's color.
    group_fig = None
    if group_data_error:
        group_plot = mo.md(f"**Couldn't read that file:** {group_data_error}")
    elif group_data is None:
        group_plot = mo.md("Choose a data series to see grouped plots.")
    elif not plot_groups:
        group_plot = mo.md("")
    elif df.empty:
        group_plot = mo.md("None of the grouped wells appear in this data file.")
    else:
        try:
            group_fig = pl.plot_grouped(
                df,
                group_plot_type.value,
                samples=None,
                facet=False,
                err=None,
                time=None,
                n_wells=group_plate.value,
                xlabel=group_axis_label,
                colors={name: g["color"] for name, g in plot_groups.items()},
                trace_mode=group_trace_mode.value,
            )
            _stats_data = pl.endpoint(df) if group_plot_type.value == "heatmap" else df
            _stats = pl.summarize_group_values(_stats_data)
            _summary_lines = [
                f"- **{row['sample']}** — mean = {row['mean']:.3g}; "
                f"median = {row['median']:.3g}; standard deviation = {row['std']:.3g}"
                for _, row in _stats.iterrows()
            ]
            _comparison_lines = []
            for _first in range(len(_stats)):
                for _second in range(_first + 1, len(_stats)):
                    _a = _stats.iloc[_first]
                    _b = _stats.iloc[_second]
                    _comparison_lines.append(
                        f"- **{_a['sample']} vs {_b['sample']}** — "
                        f"absolute difference in means = {abs(_a['mean'] - _b['mean']):.3g}; "
                        f"absolute difference in medians = {abs(_a['median'] - _b['median']):.3g}; "
                        f"absolute difference in standard deviations = {abs(_a['std'] - _b['std']):.3g}"
                    )
            _stats_view = mo.md(
                "### Group summary\n\n"
                + "\n".join(_summary_lines)
                + (
                    "\n\n### Between-group differences\n\n"
                    + "\n".join(_comparison_lines)
                    if _comparison_lines
                    else ""
                )
            )
            group_plot = mo.vstack([group_fig, _stats_view])
        except Exception as exc:
            group_plot = mo.md(f"**Couldn't draw the plot:** {exc}")
    return group_fig, group_plot


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
    # Scratch space shared between cells; writing to it redraws nothing.
    pending = {"wells": [], "error": "", "boxes": {}}
    return notes_store, pending


@app.cell
def _(mo):
    get_msg, set_msg = mo.state("", allow_self_loops=True)  # feedback line next to the Add button
    return get_msg, set_msg


@app.cell
def _():
    # A well can belong to only one group; adding it elsewhere reassigns it.
    def _well_key(w):
        try:
            return (w[0], int(w[1:]))
        except ValueError:
            return (w, 0)

    def merge_group(groups, name, wells, color):
        """Add selected wells to a group, removing them from other groups."""
        result = {key: dict(info) for key, info in groups.items()}
        wells = set(wells)
        for group_name, info in result.items():
            if group_name != name:
                info["wells"] = [
                    well for well in info.get("wells", []) if well not in wells
                ]
        current = result.get(name, {})
        result[name] = {
            **current,
            "wells": sorted(set(current.get("wells", [])) | wells, key=_well_key),
            "color": color or current.get("color"),
        }
        return result

    return (merge_group,)


@app.cell
def _(mo):
    map_note_search = mo.ui.text(
        value="",
        label="Highlight wells by note keyword",
        placeholder="e.g. control, high dose",
        full_width=True,
    )
    return (map_note_search,)


@app.cell
def _(alt, get_map, home_plate, map_note_search, mo, notes_store, pl):
    # The grouping map: same plate layout and click/drag selection as the plot picker,
    # but each well is filled with its group color (no signal values).
    # Hover over a well to see its group and that group's notes.
    _groups = get_map()
    _table = pl.plate_table(home_plate.value, _groups).copy()
    _table["col"] = _table["col"].astype(int) + 1
    _table["row"] = _table["row"].astype(int) + 1
    _table["row_label"] = [chr(64 + int(r)) for r in _table["row"]]
    _table["notes"] = _table["well"].map(
        {
            well: "; ".join(
                f"{name}: {notes_store[name]}"
                for name, group in _groups.items()
                if well in group["wells"] and notes_store.get(name)
            )
            for well in _table["well"]
        }
    )
    _keyword = map_note_search.value.strip().casefold()
    _matching_groups = {
        name
        for name, note in notes_store.items()
        if _keyword and _keyword in (note or "").casefold()
    }
    _highlight_wells = {
        well
        for name in _matching_groups
        for well in _groups.get(name, {}).get("wells", [])
    }
    _highlight_color = "#ffd54f"
    _table["note_match"] = _table["well"].isin(_highlight_wells)
    _table["fill_color"] = _table.apply(
        lambda row: (
            _highlight_color if row["note_match"] else row["group_color"]
        ),
        axis=1,
    )

    _nr, _nc = pl.plate_shape(home_plate.value)
    _cell = 34 if _nr <= 8 else 26
    _size = 700 if _nr <= 8 else 400
    _group_colors = _table.groupby("group", sort=False)["group_color"].first()
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
                "fill_color:N",
                scale=alt.Scale(
                    domain=list(
                        dict.fromkeys(
                            [
                                *_table["group_color"].tolist(),
                                _highlight_color,
                            ]
                        )
                    ),
                    range=list(
                        dict.fromkeys(
                            [
                                *_table["group_color"].tolist(),
                                _highlight_color,
                            ]
                        )
                    ),
                ),
                legend=None,
            ),
            stroke=alt.Stroke(
                "group:N",
                scale=alt.Scale(
                    domain=_group_colors.index.tolist(),
                    range=_group_colors.tolist(),
                ),
                legend=alt.Legend(title="Group"),
            ),
            strokeWidth=alt.condition(_selection, alt.value(3), alt.value(1)),
            opacity=alt.condition(_selection, alt.value(1.0), alt.value(0.35)),
            tooltip=[
                "well",
                "group",
                alt.Tooltip("notes:N", title="Notes"),
                alt.Tooltip("note_match:N", title="Keyword match"),
            ],
        )
        .add_params(_selection)
        .properties(width=_nc * _cell, height=_nr * _cell)
    )
    map_picker = mo.ui.altair_chart(_chart, chart_selection="point", legend_selection=False)
    # Pages show this wrapper, not `map_picker` itself, so clicking wells doesn't redraw the plate.
    _match_status = (
        mo.md(f"**{len(_highlight_wells)} wells highlighted** for “{_keyword}”.")
        if _keyword
        else mo.md("Search notes to fill-highlight wells whose group notes contain the keyword.")
    )
    if _highlight_wells:
        _sorted_wells = sorted(_highlight_wells, key=pl.parse_well)
        _coordinate_ranges = []
        _row_wells = {}
        for _well in _sorted_wells:
            _row, _column = pl.parse_well(_well)
            _row_wells.setdefault(_row, []).append(_column + 1)
        for _row, _columns in _row_wells.items():
            _start = _previous = _columns[0]
            for _column in _columns[1:] + [None]:
                if _column is not None and _column == _previous + 1:
                    _previous = _column
                    continue
                _row_label = chr(65 + _row)
                _coordinate_ranges.append(
                    f"{_row_label}{_start}"
                    + (f"-{_row_label}{_previous}" if _previous > _start else "")
                )
                if _column is not None:
                    _start = _previous = _column
        _coordinates = ", ".join(_coordinate_ranges)
        _coordinate_output = mo.md(
            f"**Coordinates for the grouping spectra well box:**  \n`{_coordinates}`"
        )
    elif _keyword:
        _coordinate_output = mo.md("No matching wells to list.")
    else:
        _coordinate_output = mo.md("")
    map_picker_view = map_picker
    map_note_search_view = mo.vstack([map_note_search, _match_status, _coordinate_output])
    return map_note_search_view, map_picker, map_picker_view


@app.cell
def _(home_plate, map_picker, pl):
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
    if len(_wells) == len(pl.all_wells(home_plate.value)):
        _wells = []
    map_selected = _wells
    return (map_selected,)


@app.cell
def _(get_map, map_selected, mo):
    # Selecting wells from one group opens that group's notes.
    _groups = get_map()
    _common = [
        name
        for name, group in _groups.items()
        if map_selected and all(well in group["wells"] for well in map_selected)
    ]
    active_group_picker = (
        mo.ui.dropdown(_common, value=_common[0], label="Group")
        if len(_common) > 1
        else None
    )
    active_group = (
        active_group_picker.value
        if active_group_picker is not None
        else (_common[0] if _common else None)
    )
    return active_group, active_group_picker


@app.cell
def _(active_group, active_group_picker, get_map, mo, notes_store, pending, set_map, set_msg):
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
        _contents = [_head]
        if active_group_picker is not None:
            _contents.append(active_group_picker)
        _contents.extend([_box, _save_btn])
        _panel = mo.callout(mo.vstack(_contents), kind="neutral")
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
def _(get_map, home_plate, map_inputs, map_selected, map_wells, mo, pending, pl):
    # Live hint under the notes box. Also works out which wells the Add button will use:
    # a range typed in "Wells" wins, otherwise whatever is selected on the plate.
    _wells = list(map_selected)
    _err = ""
    if map_wells.value.strip():
        try:
            _wells = pl.expand_wells(map_wells.value, home_plate.value)
        except ValueError as exc:
            _wells = []
            _err = str(exc)
    pending["wells"] = _wells
    pending["error"] = _err

    if _err:
        _hint = mo.md(f"**Invalid wells:** {_err}")
    elif _wells:
        _mine = map_inputs["name"].value.strip()
        _txt = f"**{len(_wells)} wells** ready to add. Press the green button to put them in a group."
        _reassigned = sum(
            any(name != _mine and well in group["wells"] for name, group in get_map().items())
            for well in set(_wells)
        )
        if _reassigned:
            _txt += f" {_reassigned} will be reassigned from their current groups."
        _hint = mo.md(_txt)
    else:
        _hint = mo.md("")
    map_hint = _hint
    return (map_hint,)


@app.cell
def _(get_map, get_msg, map_inputs, merge_group, mo, notes_store, pending, pl, set_map, set_msg):
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
                _result = merge_group(get_map(), _name, _wells, _color)
                if _note and _name in _result:  # a blank box keeps any notes the group already has
                    notes_store[_name] = _note
                set_map(_result)
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
def _(HOME, mo, page, workbook_summary):
    workbook_summary if page == HOME else mo.md("")
    return


@app.cell
def _(GROUPING, group_file_label, mo, page):
    group_file_label if page == GROUPING else mo.md("")
    return


@app.cell
def _(GROUPING, group_workbook_summary, mo, page):
    group_workbook_summary if page == GROUPING else mo.md("")
    return


@app.cell
def _(GROUPING, group_plot_controls, mo, page):
    group_plot_controls if page == GROUPING else mo.md("")
    return


@app.cell
def _(HOME, home_plot_controls, mo, page):
    home_plot_controls if page == HOME else mo.md("")
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
def _(GROUPING, group_note_controls, mo, page):
    group_note_controls if page == GROUPING else mo.md("")
    return


@app.cell
def _(GROUPING, group_keyword_status, mo, page):
    group_keyword_status if page == GROUPING else mo.md("")
    return


@app.cell
def _(GROUPING, group_ui, mo, page):
    group_ui if page == GROUPING else mo.md("")
    return


@app.cell
def _(GROUPING, group_plot, mo, page):
    group_plot if page == GROUPING else mo.md("")
    return


@app.cell
def _(MAPNOTES, map_picker_view, mo, page):
    map_picker_view if page == MAPNOTES else mo.md("")
    return


@app.cell
def _(MAPNOTES, map_note_search_view, mo, page):
    map_note_search_view if page == MAPNOTES else mo.md("")
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

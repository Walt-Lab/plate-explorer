# plate-explorer

Reusable plate-data analysis: pandas + numpy + matplotlib, with an interactive marimo app.

## Run
```bash
pip install -r requirements.txt
marimo edit plate_app.py      # or: marimo run plate_app.py
```
Upload one CSV/Excel file on the Home page. Its filename is shown on both the Home and Grouping-based spectra pages; uploading another file replaces the current file for the session.
The Tecan workbook importer detects kinetics, wavelength scans, and endpoint plate scans from their table structure. Endpoint plate scans default to a heatmap; kinetic and wavelength-scan data default to curves. Other vendor/export layouts may need additional format support.
The Grouping-based spectra view shows a compact mean, median, and standard deviation summary for each group, with absolute pairwise differences when multiple groups are present. Heatmap summaries use the same endpoint measurement shown in the heatmap.
On the Grouping-based spectra page, select wells on the plate or enter well coordinates, then use each group's Add/Remove control to edit its membership. A well can belong to multiple groups; adding it to a group does not remove it from other groups. Overlapping groups are shown with blended colors on the plate and analyzed independently in the curves.
Grouping map & notes offers 20 named group colors and case-insensitive note keyword highlighting. In Grouping-based spectra, enter comma-separated keywords below the plate chart and select **Add matching groups** to save each matching keyword as its own group in the graph.
If groups contain coordinates outside the currently selected plate size, the app reports which wells do not fit and suggests choosing a larger plate or editing the groups.
Each tab has its own versioned YAML import/export controls. Home exports its selected sheet, measurement, plot type, and plate size; Grouping-based spectra also exports overlapping groups and trace mode; Grouping map & notes exports its groups, colors, memberships, and notes. Importing replaces only that tab's setup. YAML stores data selections as references, not workbook contents, so upload the corresponding data file separately.

## Plate layout
One sample per line, `Name: wells`. Ranges are rectangles; combine with commas.
```
Control: A1:A3
Drug A 10uM: B1:B3, C1
```
Or in code: `pl.make_layout({"Control": "A1:A3"})`, or `pl.layout_from_file("layout.csv")` (columns `well`, `sample`, plus any extras like dose).

## Data formats (`fmt`)
- `long`: one row per well per read (columns `Well`, `Time`, `Value` - names configurable)
- `wide`: wells as rows, one column per time point
- `matrix`: endpoint read shaped like the plate

## In your own cells / scripts
```python
import platelib as pl
data = pl.load_data("export.csv", fmt="long")   # tidy DataFrame
df = pl.attach_layout(data, pl.make_layout({"Control": "A1:A3"}))
pl.summarize(df)                                # mean/sd/sem/n per sample & time
pl.plot_grouped(df, "bar", samples=["Control"])
```
Plot types: `curves`, `bar`, `box`, `heatmap`.

# plate-explorer

Reusable plate-data analysis: pandas + numpy + matplotlib, with an interactive marimo app.

## Run
```bash
pip install -r requirements.txt
marimo edit plate_app.py      # or: marimo run plate_app.py
```
Select a workbook from the `data/` folder or upload a CSV/Excel file.

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

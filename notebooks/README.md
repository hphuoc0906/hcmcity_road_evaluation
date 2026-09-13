# Research notebooks

The original exploration, kept as a record of how the analysis was developed. They were run
on Kaggle, so the paths inside them point at `/kaggle/input/...` and will not resolve here.

Everything in them has been reworked into `src/roadnet` — use the package and its CLI for
anything you intend to run. Outputs have been stripped; the notebooks are code only.

| Notebook | What it explored |
| -------- | ---------------- |
| `convert_map.ipynb` | clipping the Vietnam OSM extract to the city and building the graph |
| `processch.ipynb` | the Contraction Hierarchies implementation, benchmarks and betweenness |
| `plot_and_convert.ipynb` | first pass at exporting GeoJSON for the map |

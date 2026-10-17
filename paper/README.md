# Research paper: analysis code and data

This folder reproduces every number and figure in the paper on count-based versus rate-based rankings of Indian food-export rejections.

- `data.json` the frozen snapshot used in the paper: 1,519 EU (RASFF) and US (FDA) rejection records, 29 Aug 2024 to 27 Aug 2026, in 15 product categories, with FY2024-25 export values for 11 of them. It is not updated by the daily job.
- `analysis.py` the statistics (Spearman correlation, bootstrap, permutation test, Poisson simulation, sensitivity checks). Uses a fixed random seed, so it gives identical results every time. Writes `results.json`.
- `make_figures.py` draws Figures 1 and 2 from `results.json`.
- `results.json` the full output.

To run (needs Python 3 with numpy, scipy and matplotlib):

    pip install numpy scipy matplotlib
    python analysis.py
    python make_figures.py

Figures 1 and 2 are written next to the scripts.

# tools/viz

Generates the four graphics in `docs/images/`, light and dark, SVG and PNG.

    python3 c1_rating.py && python3 c2_gates.py && python3 c3_arch.py && python3 c4_r103.py
    python3 raster.py          # rasterises out/*.svg to 2x PNG via Playwright/Chromium

Every number rendered is sourced: the rating series is the dashboard's own history,
the gate figures come from the `results.txt` named on each row, and the round 103
position, node counts and evaluations come from `tools/probe/FINDINGS.md`.

Colours follow a validated palette — categorical hues in fixed order, status colours
reserved and always paired with an icon and a word so nothing depends on colour alone.
Dark mode is a selected set of steps for the dark surface, not an inverted light one.

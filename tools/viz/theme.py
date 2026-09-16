"""Shared theme tokens and SVG helpers for the AI Chessathon portfolio graphics.

Palette values come from the dataviz skill's reference palette. Dark steps are
selected for the dark surface, not an automatic inversion of the light ones.
"""

THEMES = {
    "light": {
        "surface": "#fcfcfb", "page": "#f9f9f7",
        "ink": "#0b0b0b", "secondary": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7",
        "series1": "#2a78d6", "series2": "#eb6834", "series3": "#1baf7a",
        "good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b",
        "band": "#f0efec",
        "sq_light": "#efeee8", "sq_dark": "#d3d2c8",
    },
    "dark": {
        "surface": "#1a1a19", "page": "#0d0d0d",
        "ink": "#ffffff", "secondary": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835",
        "series1": "#3987e5", "series2": "#d95926", "series3": "#199e70",
        "good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b",
        "band": "#26261f",
        "sq_light": "#46463f", "sq_dark": "#31312b",
    },
}

# Broad stacks so the SVGs render correctly off this machine too.
SANS = "Inter,'Helvetica Neue',Helvetica,Arial,'DejaVu Sans',sans-serif"
MONO = "'SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
CHESS = "'DejaVu Sans','Arial Unicode MS','Apple Symbols','Segoe UI Symbol',sans-serif"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, fill, size=16, weight=400, anchor="start", family=SANS,
         spacing=None, opacity=None, extra=None):
    attrs = [
        f'x="{x:.1f}"', f'y="{y:.1f}"', f'fill="{fill}"',
        f'font-family="{family}"', f'font-size="{size}"', f'font-weight="{weight}"',
        f'text-anchor="{anchor}"',
    ]
    if spacing is not None:
        attrs.append(f'letter-spacing="{spacing}"')
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    return f'<text {" ".join(attrs)}>{esc(s)}</text>'


def line(x1, y1, x2, y2, stroke, width=1, dash=None, cap="butt", opacity=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' opacity="{opacity}"' if opacity is not None else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}" stroke-linecap="{cap}"{d}{o}/>')


def rect(x, y, w, h, fill, rx=0, stroke=None, sw=1, opacity=None, dash=None):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    o = f' opacity="{opacity}"' if opacity is not None else ""
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{fill}" rx="{rx}"{s}{o}{d}/>')


def circle(cx, cy, r, fill, stroke=None, sw=2):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"{s}/>'


def svg_open(w, h, t):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-kerning="normal">'
            + rect(0, 0, w, h, t["page"]))


def footer(w, h, t, left, right="github.com/le-fische/aichessathon"):
    return (text(64, h - 34, left, t["muted"], 15)
            + text(w - 64, h - 34, right, t["muted"], 15, anchor="end", family=MONO))

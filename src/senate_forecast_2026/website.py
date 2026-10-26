#### Preamble ####
# Purpose: The website's building blocks (index.qmd): number formats, the page's colours, plain HTML tables and
#          bars, a menu that shows one of several views, and our style for plotly charts. Only presentation: the
#          numbers they show come from the summary files made by scripts/12-summarize_results.py.
# Author: Furkan Danisman
# Date: 25 October 2026
# Pre-requisites: none

import html
import re

from IPython.display import HTML

DEM, REP, IND = "#2a5db0", "#c8342b", "#6b4c9a"
INK, MUTED, RULE, LIGHT_RULE = "#14233a", "#5c6b7e", "#0b1f3a", "#dbe5ec"
PARTY_COLOURS = {"Democrat": DEM, "Republican": REP, "Independent": IND}
# Answers that are not a party: shades of grey, darkest first.
OTHER_COLOURS = {"Other": "#7f8c99", "Undecided": "#b4c0cb", "Would not vote": "#dbe2e8"}
FONT = {"family": "Public Sans, system-ui, sans-serif", "size": 13, "color": INK}


def pct(share, digits=0):
    """A share as a percentage, e.g. 0.374 -> "37%"."""
    return f"{100 * share:.{digits}f}%"


def interval(lower, upper, as_percent=False, digits=0, label=True):
    """An interval written next to its estimate, e.g. "[43, 56] 95% interval"; without the label ("[43, 56]") where
    a column's header already says it is a 95% interval."""
    if as_percent:
        shown = f"[{100 * lower:.{digits}f}, {100 * upper:.{digits}f}]"
    else:
        shown = f"[{lower:.0f}, {upper:.0f}]"
    return f"{shown} 95% interval" if label else shown


def colour_of(party):
    return PARTY_COLOURS.get(party, OTHER_COLOURS.get(party, MUTED))


def coloured_share(share, digits=0):
    """A Republican share of the vote, red when above half and blue when below."""
    colour = REP if share > 0.5 else DEM
    return f'<span style="color:{colour}">{pct(share, digits)}</span>'


def last_name(candidate):
    return candidate.split()[-1]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def split_bar(parts, thin=False):
    """A bar split into parts, each (label, share, colour); a part's label is written in it when there is room."""
    cells = []
    for label, share, colour in parts:
        if share <= 0:
            continue
        light = colour in OTHER_COLOURS.values()
        text = html.escape(label) if share >= 0.16 and not thin else ""
        cells.append(
            f'<div class="part" style="width:{100 * share:.2f}%;background:{colour};color:{INK if light else "#fff"}"'
            f' title="{html.escape(label)}">{text}</div>'
        )
    return f'<div class="split-bar{" thin" if thin else ""}">{"".join(cells)}</div>'


def table(headers, rows, numeric_from=1, css_class=""):
    """A plain HTML table: `headers` are the column names, `rows` lists of cells (already HTML). Columns from
    `numeric_from` on are right-aligned numbers."""
    def cell(tag, value, column):
        align = ' class="num"' if column >= numeric_from else ""
        return f"<{tag}{align}>{value}</{tag}>"

    head = "".join(cell("th", html.escape(h), i) for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(cell("td", v, i) for i, v in enumerate(row)) + "</tr>" for row in rows)
    return f'<table class="plain {css_class}" data-quarto-disable-processing="true"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def folded(summary, content):
    """`content` hidden under a line the reader can click to open it."""
    return f'<details class="folded"><summary>{html.escape(summary)}</summary>{content}</details>'


def choices(name, views, as_buttons=False, picker=True):
    """Several views of which one is shown at a time, picked from a menu (or from buttons, for a few views).
    `views` maps each view's label to its HTML. With picker=False there is no menu here: another menu with the same
    `name` (e.g. the version menu at the top of the page) switches them. The page's script (in index.qmd) does it."""
    labels = list(views)
    if not picker:
        menu = ""
    elif as_buttons:
        menu = '<div class="choice-buttons" role="tablist">' + "".join(
            f'<button type="button" data-choice="{name}" data-value="{slug(label)}"'
            f'{" class=active" if i == 0 else ""}>{html.escape(label)}</button>'
            for i, label in enumerate(labels)
        ) + "</div>"
    else:
        menu = choice_menu(name, labels)
    panels = "".join(
        f'<div class="choice-view" data-choice-view="{name}" data-value="{slug(label)}"'
        f'{"" if i == 0 else " hidden"}>{content}</div>'
        for i, (label, content) in enumerate(views.items())
    )
    return menu + panels


def choice_menu(name, labels):
    """A menu that switches the views called `name` (see choices())."""
    return f'<select class="choice-menu" data-choice="{name}">' + "".join(
        f'<option value="{slug(label)}">{html.escape(label)}</option>' for label in labels
    ) + "</select>"


plotly_loaded = False


def figure_html(figure, height):
    """A plotly figure in our style, as HTML: no background boxes, light horizontal lines only, readable hover
    labels. plotly.js is loaded once, with the first figure on the page."""
    global plotly_loaded
    figure.update_layout(
        font=FONT, height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": figure.layout.margin.r or 0, "t": figure.layout.margin.t or 10, "b": 0}, showlegend=False,
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": LIGHT_RULE, "font": {"family": FONT["family"], "size": 13, "color": INK}},
    )
    figure.update_xaxes(showgrid=False, zeroline=False, showline=True, linecolor=INK, ticks="outside",
                        tickcolor=INK, tickfont={"color": MUTED, "size": 12})
    figure.update_yaxes(gridcolor=LIGHT_RULE, zeroline=False, tickfont={"color": MUTED, "size": 12})
    include = "cdn" if not plotly_loaded else False
    plotly_loaded = True
    return figure.to_html(full_html=False, include_plotlyjs=include,
                          config={"displayModeBar": False, "responsive": True})


def show(*pieces):
    """Put HTML pieces on the page."""
    return HTML("".join(pieces))

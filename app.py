import sys
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    DEFAULT_WORKBOOK, MIN_OBSERVATIONS, OUTLIER_GAP, PARAMETER_SHEET,
    RETURN_SHEET, SIGNIFICANCE_LEVEL,
)
from src.cleaner import clean_data
from src.correlation_engine import (
    calculate_parameter_correlations, correlations_by_group,
)
from src.exporter import build_correlation_workbook, export_filename
from src.filters import apply_filters
from src.forward_returns import build_forward_dataset
from src.loader import load_workbook_data
from src.theme import APPEARANCES, build_css

st.set_page_config(page_title="MF Correlation Analytics", page_icon="▦", layout="wide")

st.session_state.setdefault("appearance", "Dark")
appearance = st.session_state["appearance"]
st.markdown(build_css(appearance), unsafe_allow_html=True)


@st.cache_data(show_spinner="Reading the Excel workbook...")
def prepare_dataset(workbook):
    parameters, returns = load_workbook_data(workbook)
    parameters, returns, parameter_columns = clean_data(parameters, returns)
    forward = build_forward_dataset(parameters, returns)
    detected = [column for column in parameter_columns if column in forward.columns]
    return forward, detected, parameters.shape, returns.shape


@st.cache_data(show_spinner="Computing correlations...")
def compute_rankings(workbook, from_year, to_year, scheme, category,
                     min_observations, significance_level, significant_only):
    dataset, parameter_columns, _, _ = prepare_dataset(workbook)
    filtered = apply_filters(dataset, from_year, to_year, scheme, category)
    results, excluded = calculate_parameter_correlations(
        filtered, parameter_columns, min_observations=min_observations,
        significance_level=significance_level, significant_only=significant_only)
    return results, excluded, int(filtered["scheme_id"].nunique()), int(len(filtered))


@st.cache_data(show_spinner="Building the per-category breakdown...")
def compute_by_category(workbook, from_year, to_year, parameters,
                        min_observations, significance_level):
    dataset, _, _, _ = prepare_dataset(workbook)
    scoped = apply_filters(dataset, from_year, to_year)
    frames = [correlations_by_group(scoped, parameter, "category",
                                   min_observations=min_observations,
                                   significance_level=significance_level)
              for parameter in parameters]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def render_ranking(results):
    rows = []
    for rank, item in enumerate(results.itertuples(index=False), 1):
        value = item.correlation
        polarity = "positive" if value >= 0 else "negative"
        significance = (f"<span class='pill pill-ok'>p = {item.p_value:.3f}</span>"
                        if item.significant else
                        f"<span class='pill pill-warn'>p = {item.p_value:.2f}</span>")
        robustness = ("<span class='pill pill-warn'>outlier-driven</span>"
                      if item.outlier_sensitive else
                      f"<span class='pill'>ρ {item.spearman:+.2f}</span>")
        rows.append(
            f"<tr><td class='rk'>{rank:02d}</td>"
            f"<td class='pname'>{escape(item.parameter)}</td>"
            f"<td class='cval {'up' if value >= 0 else 'down'}'>{value:+.3f}</td>"
            f"<td><div class='track'><span class='zero'></span>"
            f"<span class='fill {polarity}' style='width:{min(abs(value) * 50, 50):.1f}%'></span></div></td>"
            f"<td><span class='pill'>{item.strength}</span></td>"
            f"<td class='num'>{item.observations:,}</td>"
            f"<td>{significance}</td><td>{robustness}</td></tr>")
    return ("<table class='rank'><thead><tr><th>#</th><th>Parameter</th><th>Pearson</th>"
            "<th>Signal</th><th>Strength</th><th>N</th>"
            "<th title='Two-sided p-value'>Significance</th>"
            "<th title='Spearman rank correlation'>Robustness</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def render_omitted(excluded):
    rows = "".join(
        f"<tr><td class='pname'>{escape(item.parameter)}</td>"
        f"<td class='num'>{item.observations:,}</td>"
        f"<td class='reason'>{escape(str(item.excluded_reason))}</td></tr>"
        for item in excluded.itertuples(index=False))
    return ("<table class='rank'><thead><tr><th>Parameter</th><th>N</th>"
            f"<th>Reason omitted</th></tr></thead><tbody>{rows}</tbody></table>")


heading, switch = st.columns([4.6, 1])
with heading:
    st.markdown(
        '<div class="hero-line"><h1>Mutual Fund Correlation Analytics</h1>'
        '<span class="badge">Parameter T &rarr; Return T+1</span></div>',
        unsafe_allow_html=True)
with switch:
    # A plain button, not a styled radio: hiding BaseWeb's radio internals also
    # hides the real input, which leaves nothing to click.
    target = APPEARANCES[1] if appearance == APPEARANCES[0] else APPEARANCES[0]
    if st.button(f"Switch to {target}", key="appearance_switch", use_container_width=True):
        st.session_state["appearance"] = target
        st.rerun()
st.markdown(
    '<div class="hero"><p>Ranks every eligible numeric parameter by its correlation with the '
    "same scheme's return in the following year. Each coefficient carries its sample size, its "
    'two-sided p-value and a Spearman robustness check, so a figure produced by a thin or '
    'outlier-driven sample is never presented as an established result.</p></div>',
    unsafe_allow_html=True)

try:
    dataset, parameter_columns, parameter_shape, return_shape = prepare_dataset(str(DEFAULT_WORKBOOK))
except Exception as error:
    st.error(f"Could not load the workbook: {error}")
    st.stop()

if dataset.empty:
    st.warning("No scheme-year observation has a valid next-year return.")
    st.stop()

years = sorted(dataset["year"].dropna().astype(int).unique())

with st.container(border=True):
    st.markdown('<div class="kicker">Analysis scope</div>', unsafe_allow_html=True)
    top = st.columns([1, 1, 2.6, 2.1])
    from_year = top[0].selectbox("From year (T)", years, index=0)
    to_year = top[1].selectbox("To year (T)", years, index=len(years) - 1)
    scheme_options = ["All Funds"] + sorted(dataset["scheme_name"].dropna().unique().tolist())
    scheme = top[2].selectbox("Fund / Scheme", scheme_options)
    category_options = ["All Categories"] + sorted(dataset["category"].dropna().unique().tolist())
    category = top[3].selectbox("Category", category_options, disabled=scheme != "All Funds")

    bottom = st.columns([1.5, 1.5, 2.4])
    min_observations = bottom[0].number_input(
        "Minimum observations", min_value=10, max_value=500, value=MIN_OBSERVATIONS, step=5,
        help="Pearson correlations built from a small sample are unstable. The alpha and beta "
             "family is the sparsest in this workbook, so it is the first to produce spurious "
             "values when this floor is set too low.")
    significance_level = bottom[1].selectbox(
        "Significance level", [0.01, 0.05, 0.10],
        index=[0.01, 0.05, 0.10].index(SIGNIFICANCE_LEVEL),
        format_func=lambda value: f"p ≤ {value:g}")
    significant_only = bottom[2].checkbox(
        "Show statistically significant parameters only", value=False,
        help="Hides coefficients whose p-value does not clear the significance level.")

if from_year > to_year:
    st.error("**From year** must be less than or equal to **To year**.")
    st.stop()

results, excluded, fund_count, observation_count = compute_rankings(
    str(DEFAULT_WORKBOOK), from_year, to_year, scheme, category,
    int(min_observations), float(significance_level), bool(significant_only))

significant_count = int(results["significant"].sum()) if not results.empty else 0
flagged_count = int(results["outlier_sensitive"].sum()) if not results.empty else 0
strongest = results.iloc[0] if not results.empty else None
return_span = f"{from_year + 1}–{to_year + 1}"

tiles = [
    ("Funds analysed", f"{fund_count:,}", f"{observation_count:,} fund-year rows"),
    ("Parameters reported", f"{len(results):,}", f"{len(excluded):,} omitted as unreliable"),
    ("Statistically significant", f"{significant_count:,}", f"at p ≤ {significance_level:g}"),
    ("Strongest correlation",
     f"{strongest['correlation']:+.3f}" if strongest is not None else "—",
     strongest["parameter"] if strongest is not None else "No result"),
    ("Return years covered", return_span, f"parameter years {from_year}–{to_year}"),
]
for column, (label, value, sub) in zip(st.columns(5), tiles):
    column.markdown(
        f'<div class="kpi"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{escape(str(sub))}</div></div>', unsafe_allow_html=True)

if flagged_count or (not results.empty and significant_count < len(results)):
    parts = []
    if significant_count < len(results):
        parts.append(f"<b>{len(results) - significant_count}</b> reported coefficient(s) "
                     f"are not significant at p ≤ {significance_level:g}")
    if flagged_count:
        parts.append(f"<b>{flagged_count}</b> are outlier-driven "
                     f"(|Pearson − Spearman| ≥ {OUTLIER_GAP})")
    st.markdown(f'<div class="callout">Read with care: {" and ".join(parts)}. '
                'Treat these as unconfirmed rather than as findings.</div>',
                unsafe_allow_html=True)

st.markdown(
    '<div class="section-head"><div><h2>Parameter ranking</h2>'
    "<p>Ranked by the absolute strength of the correlation with the same scheme's "
    'next-year return</p></div>'
    f'<div class="section-count">{len(parameter_columns):,} parameters in the workbook</div></div>',
    unsafe_allow_html=True)

controls = st.columns([3.4, 1.15, 1.5])
search = controls[0].text_input("Search", placeholder="Search parameters…",
                                label_visibility="collapsed")
top_n = controls[1].selectbox("Show", ["Top 10", "Top 20", "Top 50", "All"], index=3,
                             label_visibility="collapsed")

display = (results[results["parameter"].str.contains(search, case=False, na=False)]
           if search else results)
if top_n != "All":
    display = display.head(int(top_n.split()[1]))

with controls[2]:
    if results.empty:
        st.button("Download Excel", disabled=True, use_container_width=True)
    else:
        by_category = None
        if scheme == "All Funds" and category == "All Categories":
            by_category = compute_by_category(
                str(DEFAULT_WORKBOOK), from_year, to_year,
                tuple(results["parameter"].tolist()),
                int(min_observations), float(significance_level))
        st.download_button(
            "Download Excel",
            data=build_correlation_workbook(
                results, from_year, to_year, category, scheme,
                by_category=by_category, excluded=excluded,
                min_observations=int(min_observations),
                significance_level=float(significance_level)),
            file_name=export_filename(from_year, to_year, category, scheme),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Year range, category, parameter name and correlation for every "
                 "reported parameter, plus a per-category breakdown.")

if display.empty:
    st.info("No parameter meets the current thresholds. Lower the minimum observation "
            "count, widen the year range, or clear the significance filter.")
else:
    st.markdown(
        f'<div class="panel">{render_ranking(display)}'
        f'<div class="meta">Showing {len(display):,} of {len(results):,} reported parameters '
        f'· pairwise complete observations · minimum N = {int(min_observations)} '
        f'· significance at p ≤ {significance_level:g}</div></div>',
        unsafe_allow_html=True)

if not excluded.empty:
    with st.expander(f"Omitted parameters ({len(excluded):,})"):
        st.markdown(render_omitted(excluded), unsafe_allow_html=True)

with st.expander("Methodology and data notes"):
    st.markdown(f"""
**Pairing.** A parameter observed in year **T** is matched to the same `scheme_id`'s return in
year **T+1**. The current scope covers parameter years **{from_year}–{to_year}** against return
years **{return_span}**. The final parameter year is dropped when its next-year return is
unavailable.

**Coefficient.** Pearson correlation over pairwise complete observations. Missing values are
never imputed and non-finite values are dropped. A parameter is reported only when it clears the
minimum observation floor and both series carry real variance.

**Why the floor matters.** A Pearson coefficient from a handful of fund-years is noise. The alpha
and beta family carries the most missing data in this workbook, so it is the first to produce
large, unstable values on a narrow slice. The floor and the p-value together keep those out of
the ranking.

**Robustness.** Spearman's rank correlation (ρ) is computed alongside Pearson. When the two
differ by {OUTLIER_GAP} or more, a small number of extreme values is driving the linear
coefficient and the row is flagged as outlier-driven.

**Sources.** Sheets `{PARAMETER_SHEET}` and `{RETURN_SHEET}`. Loaded {parameter_shape[0]:,}
parameter rows and {return_shape[0]:,} return rows; {len(parameter_columns):,} numeric parameters
detected automatically.
""")

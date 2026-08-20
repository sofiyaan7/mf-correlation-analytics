# Mutual Fund Forward Return Correlation Analytics

A Streamlit dashboard that ranks every eligible numeric mutual-fund parameter by its
correlation with the **same scheme's return in the following year**.

## Run

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

The application reads `Correlation file_rishil_Maker 1.xlsx` from the project root, using the
workbook's `Parameter data` sheet (annual parameter blocks, 2005-2022) and `Return data` sheet
(annual returns, 2006-2023).

## Accuracy

The pooled full-range coefficients reproduce the workbook's own `Summary` sheet **exactly** for
all 24 parameters that sheet reports (maximum absolute difference 1.2e-15). That check is the
regression test for any change to the loader, the cleaner, or the engine.

Three rules earn that agreement and keep sliced views honest:

- **Zero is not always zero.** `Average Drawdown`, `Average Loss` and `Calmar Ratio` average or
  divide over a *subset* of periods. A stored `0.0` means the subset was empty -- no drawdown, or
  no losing period, that year -- so the statistic is undefined. The source export emits `0.0`;
  the workbook's own per-ratio sheets leave those cells blank and compute `Summary` without them.
  `src/cleaner.py` restores them to missing.
- **A minimum sample size.** A Pearson coefficient built from a handful of fund-years is noise.
  The alpha and beta family carries the most missing data here (`Bear Beta` has 901 paired
  observations against `Average (Annualized)`'s 2,489), so it is the first to throw off large,
  unstable values on a narrow slice. A single fund has at most 18 observations, which is why
  selecting one now reports nothing rather than 98 spurious correlations.
- **Significance and robustness travel with every number.** Each coefficient carries its
  two-sided p-value and a Spearman rank correlation. When Pearson and Spearman diverge by 0.15 or
  more, a few extreme values are driving the linear figure and the row is flagged
  *outlier-driven* -- `Calmar Ratio`, for instance, is -0.10 by Pearson but -0.54 by Spearman
  because one observation reaches 1,890.

## Data rules

- Parameter year `T` is joined to the same `scheme_id` and return year `T + 1`.
- The final parameter year is omitted when its next-year return is unavailable.
- Numeric parameters are detected from the workbook at load time.
- Missing values are never imputed; pairwise complete observations are used.
- Parameters are reported only when they clear the observation floor and both series carry
  variance. Everything else is listed under *Omitted parameters* with the reason.

## Excel export

**Download Excel** produces a workbook whose every row carries the year range, the category, the
parameter name and its correlation, so a row stays meaningful once copied elsewhere:

| Sheet | Contents |
| --- | --- |
| `Correlations` | One row per reported parameter for the current selection |
| `By Category` | The same parameters broken out per category (all-funds, all-categories scope) |
| `Omitted` | Parameters excluded, with the reason |
| `Methodology` | Scope, thresholds and the meaning of each flag |

Each sheet carries correlation, Spearman, observations, p-value, significance, strength,
direction and the outlier-sensitivity flag.

## Layout

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit UI: filters, KPIs, ranking table, export |
| `config.py` | Workbook path, observation floor, significance level, outlier gap |
| `src/loader.py` | Reads the two workbook sheets into tidy frames |
| `src/cleaner.py` | Types, de-duplicates, and restores zero placeholders to missing |
| `src/forward_returns.py` | Joins parameter year `T` to return year `T + 1` |
| `src/correlation_engine.py` | The single source of every coefficient in the app |
| `src/filters.py` | Year, scheme and category scoping |
| `src/exporter.py` | Builds the downloadable workbook |

## Appearance

The theme is pinned in `.streamlit/config.toml` so the page never inherits the operating
system's light/dark preference — without it, Streamlit renders its own widgets dark on a dark
desktop while the stylesheet paints light panels. Both palettes live in `src/theme.py` and are
verified against WCAG AA for body text; the switch sits at the top right.

`streamlit` is pinned in `requirements.txt` because that stylesheet targets `data-testid`
attributes in Streamlit's DOM, which are internal and change between releases. Upgrading
Streamlit means re-checking the theme in a browser.

## Deploy

The repository is private and the workbook is committed, so the app runs as-is.

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with the GitHub account that owns
   this repository and grant access to private repositories when prompted.
2. **Create app → Deploy a public app from GitHub**, then set:
   - Repository: `sofiyaan7/mf-correlation-analytics`
   - Branch: `main`
   - Main file path: `app.py`
3. Under **Advanced settings**, choose Python 3.11 or 3.12.

**Restrict who can view it.** A Community Cloud app is reachable by anyone with the URL even when
the repository is private, and this workbook holds internal fund research. After the first deploy,
open **Settings → Sharing** and either invite specific viewers by email or set the app to private
so the data is not served to the public.

The first load parses the 19 MB workbook and is slow; `st.cache_data` keeps subsequent
interactions fast. Free-tier instances have about 1 GB of memory, which is comfortable for this
dataset.

"""Correlation statistics between a parameter in year T and the same scheme's
return in year T+1.

Every view in the application (ranking, category breakdown, year breakdown,
Excel export) is computed through `correlation_stats` so that no two views can
ever disagree about the same number.

Accuracy rules applied here:

* Pairwise complete observations only -- missing values are never imputed.
* Non-finite values are dropped rather than silently coerced.
* A result is reported only when it clears `min_observations` AND both series
  carry real variance; otherwise the reason for exclusion is recorded.
* A two-sided p-value accompanies every coefficient, so a coefficient produced
  by a handful of points is no longer presented as if it were established.
* Spearman is computed alongside Pearson. A large gap between the two means the
  Pearson figure is being driven by a few extreme values and is flagged.
"""

import numpy as np
import pandas as pd
from scipy import stats

from config import OUTLIER_GAP

MIN_VARIANCE = 1e-12

RESULT_COLUMNS = [
    "parameter", "correlation", "abs_correlation", "spearman", "p_value",
    "observations", "direction", "strength", "significant", "outlier_sensitive",
    "robust_gap", "excluded_reason",
]


def correlation_strength(value):
    absolute = abs(value)
    if absolute >= 0.7:
        return "Very strong"
    if absolute >= 0.5:
        return "Strong"
    if absolute >= 0.3:
        return "Moderate"
    if absolute >= 0.1:
        return "Weak"
    return "Negligible"


def _pairwise(dataframe, parameter, target_column):
    """Return the finite, complete (x, y) pairs as float64 arrays."""
    pair = dataframe.loc[:, [parameter, target_column]]
    if isinstance(pair, pd.Series):
        pair = pair.to_frame()
    pair = pair.apply(pd.to_numeric, errors="coerce")
    pair = pair.replace([np.inf, -np.inf], np.nan).dropna()
    values = pair.to_numpy(dtype="float64", copy=False)
    return values[:, 0], values[:, 1]


def _blank(parameter, observations, reason):
    return {
        "parameter": parameter, "correlation": np.nan, "abs_correlation": np.nan,
        "spearman": np.nan, "p_value": np.nan, "observations": observations,
        "direction": None, "strength": None, "significant": False,
        "outlier_sensitive": False, "robust_gap": np.nan, "excluded_reason": reason,
    }


def correlation_stats(dataframe, parameter, target_column="next_year_return",
                      min_observations=30, significance_level=0.05):
    """Full statistics for one parameter against the next-year return."""
    x, y = _pairwise(dataframe, parameter, target_column)
    observations = int(x.size)

    if observations < min_observations:
        return _blank(parameter, observations, f"Fewer than {min_observations} paired observations")
    if x.var() <= MIN_VARIANCE or y.var() <= MIN_VARIANCE:
        return _blank(parameter, observations, "No variance in the parameter or the return")

    pearson, p_value = stats.pearsonr(x, y)
    if not np.isfinite(pearson):
        return _blank(parameter, observations, "Correlation is undefined")

    spearman = stats.spearmanr(x, y).statistic
    spearman = float(spearman) if np.isfinite(spearman) else np.nan
    gap = abs(pearson - spearman) if np.isfinite(spearman) else np.nan

    return {
        "parameter": parameter,
        "correlation": float(pearson),
        "abs_correlation": abs(float(pearson)),
        "spearman": spearman,
        "p_value": float(p_value),
        "observations": observations,
        "direction": "Positive" if pearson > 0 else "Negative",
        "strength": correlation_strength(pearson),
        "significant": bool(p_value <= significance_level),
        "outlier_sensitive": bool(np.isfinite(gap) and gap >= OUTLIER_GAP),
        "robust_gap": float(gap) if np.isfinite(gap) else np.nan,
        "excluded_reason": None,
    }


def calculate_parameter_correlations(dataframe, parameter_columns,
                                     target_column="next_year_return",
                                     min_observations=30, significance_level=0.05,
                                     significant_only=False):
    """Rank every parameter by the absolute strength of its correlation.

    Returns (results, excluded): `results` holds the parameters that produced a
    usable coefficient, ranked strongest first; `excluded` explains the rest.
    """
    reported, excluded = [], []
    for parameter in parameter_columns:
        if parameter not in dataframe.columns or parameter == target_column:
            continue
        record = correlation_stats(dataframe, parameter, target_column,
                                   min_observations, significance_level)
        (excluded if record["excluded_reason"] else reported).append(record)

    results = pd.DataFrame(reported, columns=RESULT_COLUMNS)
    if significant_only and not results.empty:
        moved = results[~results["significant"]].copy()
        moved["excluded_reason"] = f"Not significant at p <= {significance_level:g}"
        excluded.extend(moved.to_dict("records"))
        results = results[results["significant"]]
    results = results.sort_values("abs_correlation", ascending=False, ignore_index=True)

    excluded_frame = pd.DataFrame(excluded, columns=RESULT_COLUMNS)
    if not excluded_frame.empty:
        excluded_frame = excluded_frame.sort_values(
            ["observations", "parameter"], ascending=[False, True], ignore_index=True)
    return results, excluded_frame


def correlations_by_group(dataframe, parameter, group_column,
                          target_column="next_year_return",
                          min_observations=30, significance_level=0.05):
    """One row of statistics per value of `group_column` for a single parameter."""
    rows = []
    for group, frame in dataframe.groupby(group_column, dropna=False, observed=True):
        record = correlation_stats(frame, parameter, target_column,
                                  min_observations, significance_level)
        record[group_column] = group if pd.notna(group) else "Unclassified"
        rows.append(record)
    columns = [group_column] + RESULT_COLUMNS
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return frame
    return frame.sort_values(group_column, ignore_index=True)


def parameter_detail(dataframe, parameter, min_observations=30, significance_level=0.05):
    """The observation-level rows behind one parameter, plus its statistics."""
    identifiers = [column for column in
                   ("scheme_name", "category", "year", "target_year")
                   if column in dataframe.columns]
    detail = dataframe.loc[:, identifiers + [parameter, "next_year_return"]].copy()
    detail = detail.rename(columns={parameter: "parameter_value"})
    detail["parameter_value"] = pd.to_numeric(detail["parameter_value"], errors="coerce")
    detail["next_year_return"] = pd.to_numeric(detail["next_year_return"], errors="coerce")
    detail = detail.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["parameter_value", "next_year_return"])
    if "year" in detail.columns:
        detail["parameter_year"] = detail["year"]
    if "target_year" in detail.columns:
        detail["return_year"] = detail["target_year"]
    record = correlation_stats(dataframe, parameter, "next_year_return",
                              min_observations, significance_level)
    return detail, record

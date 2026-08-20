"""Excel export of parameter correlations.

Produces a workbook whose every row carries the year range, the category, the
parameter name and its correlation, so a row remains meaningful once it is
copied out of the sheet it came from.
"""

from io import BytesIO

import pandas as pd

SHEET_COLUMNS = [
    "Year Range", "Category", "Parameter", "Correlation", "Spearman",
    "Observations", "P-Value", "Significant", "Strength", "Direction",
    "Outlier Sensitive",
]


def _year_range(from_year, to_year):
    return f"{from_year}" if from_year == to_year else f"{from_year}-{to_year}"


def _shape(results, year_range, category):
    """Reduce an engine result frame to the export column set."""
    if results.empty:
        return pd.DataFrame(columns=SHEET_COLUMNS)
    frame = pd.DataFrame({
        "Year Range": year_range,
        "Category": category,
        "Parameter": results["parameter"],
        "Correlation": results["correlation"].round(6),
        "Spearman": results["spearman"].round(6),
        "Observations": results["observations"],
        "P-Value": results["p_value"].round(6),
        "Significant": results["significant"].map({True: "Yes", False: "No"}),
        "Strength": results["strength"],
        "Direction": results["direction"],
        "Outlier Sensitive": results["outlier_sensitive"].map({True: "Yes", False: "No"}),
    })
    return frame.reset_index(drop=True)


def build_correlation_workbook(results, from_year, to_year, category, scheme,
                               by_category=None, excluded=None,
                               min_observations=30, significance_level=0.05):
    """Return the bytes of an .xlsx workbook describing the current selection."""
    year_range = _year_range(from_year, to_year)
    selection = _shape(results, year_range, category)

    notes = pd.DataFrame({
        "Field": [
            "Year range (parameter year T)", "Return years covered", "Category",
            "Fund / Scheme", "Parameters reported", "Minimum observations",
            "Significance level", "Method", "Pairing rule", "Missing values",
            "Outlier Sensitive", "Significant",
        ],
        "Value": [
            year_range, _year_range(from_year + 1, to_year + 1), category, scheme,
            len(selection), min_observations, f"p <= {significance_level:g}",
            "Pearson correlation, with Spearman as a robustness check",
            "Parameter in year T against the same scheme's return in year T+1",
            "Never imputed; pairwise complete observations only",
            "Yes when |Pearson - Spearman| >= 0.15, meaning a few extreme values drive the coefficient",
            "Yes when the two-sided p-value clears the significance level",
        ],
    })

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        selection.to_excel(writer, sheet_name="Correlations", index=False)
        if by_category is not None and not by_category.empty:
            rows = by_category[by_category["excluded_reason"].isna()]
            frames = [_shape(frame, year_range, name)
                      for name, frame in rows.groupby("category", observed=True)]
            if frames:
                combined = pd.concat(frames, ignore_index=True)
                combined = combined.sort_values(
                    ["Parameter", "Category"], ignore_index=True)
                combined.to_excel(writer, sheet_name="By Category", index=False)
        if excluded is not None and not excluded.empty:
            omitted = pd.DataFrame({
                "Year Range": year_range, "Category": category,
                "Parameter": excluded["parameter"],
                "Observations": excluded["observations"],
                "Reason Omitted": excluded["excluded_reason"],
            })
            omitted.to_excel(writer, sheet_name="Omitted", index=False)
        notes.to_excel(writer, sheet_name="Methodology", index=False)
        _autofit(writer)
    return buffer.getvalue()


def _autofit(writer):
    """Widen columns and freeze the header row on every sheet."""
    for worksheet in writer.book.worksheets:
        worksheet.freeze_panes = "A2"
        for column in worksheet.columns:
            longest = max((len(str(cell.value)) for cell in column
                           if cell.value is not None), default=10)
            letter = column[0].column_letter
            worksheet.column_dimensions[letter].width = min(max(longest + 2, 11), 52)


def export_filename(from_year, to_year, category, scheme):
    parts = ["parameter_correlations", _year_range(from_year, to_year)]
    if scheme and scheme != "All Funds":
        parts.append(scheme)
    elif category and category != "All Categories":
        parts.append(category)
    slug = "_".join("".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in part).strip("_") for part in parts)
    return f"{slug}.xlsx"

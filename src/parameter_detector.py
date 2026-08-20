import numpy as np
import pandas as pd


EXCLUDED_COLUMNS = {
    "scheme_id", "scheme_name", "isin", "category", "sub-category", "year",
    "date", "return", "return_year", "target_year", "next_year_return",
}


def detect_parameter_columns(dataframe):
    parameters = []
    for column in dataframe.columns:
        if column.lower().strip() in EXCLUDED_COLUMNS:
            continue
        values = pd.to_numeric(dataframe[column], errors="coerce")
        if values.notna().any() and np.isfinite(values.dropna()).all():
            parameters.append(column)
    return parameters

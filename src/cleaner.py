import pandas as pd

IDENTIFIER_COLUMNS = {"scheme_id", "scheme_name", "category", "year"}

# Metrics that average or divide over a *subset* of periods. A stored 0.0 means
# the subset was empty -- the fund had no drawdown, or no losing period, in that
# year -- so the statistic is undefined rather than zero. The source export
# emits 0.0; the workbook's own per-ratio sheets leave those cells blank, and the
# `Summary` correlations are computed with them excluded. Keeping the zeros would
# feed a handful of false data points into every affected coefficient.
UNDEFINED_WHEN_ZERO = ("Average Drawdown", "Average Loss", "Calmar Ratio")


def clean_data(parameters, returns):
    parameters = parameters.copy()
    returns = returns.copy()
    for frame in (parameters, returns):
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
        frame["scheme_id"] = frame["scheme_id"].astype(str).str.strip()
        frame["scheme_name"] = frame["scheme_name"].astype("string").str.strip()
        frame["category"] = frame["category"].astype("string").str.strip()

    parameter_columns = [column for column in parameters.columns
                         if column not in IDENTIFIER_COLUMNS]
    for column in parameter_columns:
        parameters[column] = pd.to_numeric(parameters[column], errors="coerce")
    for column in UNDEFINED_WHEN_ZERO:
        if column in parameters.columns:
            parameters.loc[parameters[column] == 0, column] = pd.NA

    returns["return"] = pd.to_numeric(returns["return"], errors="coerce")
    parameters = parameters.drop_duplicates(["scheme_id", "year"], keep="first")
    returns = returns.drop_duplicates(["scheme_id", "year"], keep="first")
    return parameters, returns, parameter_columns

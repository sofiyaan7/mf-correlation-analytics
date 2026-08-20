from pathlib import Path

import pandas as pd

from config import DEFAULT_WORKBOOK, PARAMETER_SHEET, RETURN_SHEET


def _normalise_text(value):
    if pd.isna(value):
        return None
    return " ".join(str(value).replace("\n", " ").split()).strip()


def _category_and_scheme_rows(raw, name_col, id_col):
    categories = {}
    schemes = {}
    current_category = "Unclassified"
    for row_number in range(len(raw)):
        name = raw.iat[row_number, name_col]
        identifier = raw.iat[row_number, id_col]
        if pd.notna(name) and pd.isna(identifier):
            current_category = _normalise_text(name) or current_category
        elif pd.notna(name) and pd.notna(identifier):
            key = str(identifier).strip()
            categories[key] = current_category
            schemes[key] = _normalise_text(name)
    return categories, schemes


def _read_returns(workbook):
    raw = pd.read_excel(workbook, sheet_name=RETURN_SHEET, header=None)
    year_row = 7
    header_row = 9
    years = {
        column: int(pd.Timestamp(raw.iat[year_row, column]).year)
        for column in range(2, raw.shape[1])
        if pd.notna(raw.iat[year_row, column])
    }
    categories, schemes = _category_and_scheme_rows(raw, 0, 1)
    records = []
    for row_number in range(header_row + 1, len(raw)):
        identifier = raw.iat[row_number, 1]
        if pd.isna(identifier):
            continue
        key = str(identifier).strip()
        for column, year in years.items():
            records.append(
                {
                    "scheme_id": key,
                    "scheme_name": schemes.get(key, _normalise_text(raw.iat[row_number, 0])),
                    "category": categories.get(key, "Unclassified"),
                    "year": year,
                    "return": raw.iat[row_number, column],
                }
            )
    returns = pd.DataFrame(records)
    returns["return"] = pd.to_numeric(returns["return"], errors="coerce")
    return returns.replace([float("inf"), float("-inf")], pd.NA)


def _read_parameters(workbook):
    raw = pd.read_excel(workbook, sheet_name=PARAMETER_SHEET, header=None)
    block_starts = [3 + 101 * index for index in range(18)]
    years = {
        start: int(pd.Timestamp(raw.iat[6, start]).year)
        for start in block_starts
        if pd.notna(raw.iat[6, start])
    }
    parameter_names = {
        column: _normalise_text(raw.iat[8, column])
        for column in range(3, 104)
        if pd.notna(raw.iat[8, column])
    }
    categories, schemes = _category_and_scheme_rows(raw, 1, 2)
    records = []
    for row_number in range(10, len(raw)):
        identifier = raw.iat[row_number, 2]
        if pd.isna(identifier):
            continue
        key = str(identifier).strip()
        for start, year in years.items():
            record = {
                "scheme_id": key,
                "scheme_name": schemes.get(key, _normalise_text(raw.iat[row_number, 1])),
                "category": categories.get(key, "Unclassified"),
                "year": year,
            }
            for offset, name in enumerate(parameter_names.values()):
                record[name] = raw.iat[row_number, start + offset]
            records.append(record)
    parameters = pd.DataFrame(records)
    return parameters.replace([float("inf"), float("-inf")], pd.NA)


def load_workbook_data(workbook=DEFAULT_WORKBOOK):
    workbook = Path(workbook)
    if not workbook.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook}")
    parameters = _read_parameters(workbook)
    returns = _read_returns(workbook)
    return parameters, returns

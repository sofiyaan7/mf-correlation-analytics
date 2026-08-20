import pandas as pd


def build_forward_dataset(parameters, returns):
    target = returns[["scheme_id", "year", "return"]].rename(
        columns={"year": "target_year", "return": "next_year_return"}
    )
    target["year"] = target["target_year"] - 1
    merged = parameters.merge(target, on=["scheme_id", "year"], how="left", validate="many_to_one")
    return merged[merged["next_year_return"].notna()].copy()

def apply_filters(dataframe, from_year, to_year, scheme="All Funds", category="All Categories"):
    filtered = dataframe[dataframe["year"].between(from_year, to_year)].copy()
    if scheme != "All Funds":
        filtered = filtered[filtered["scheme_name"] == scheme]
    if category != "All Categories" and scheme == "All Funds":
        filtered = filtered[filtered["category"] == category]
    return filtered

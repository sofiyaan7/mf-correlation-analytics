from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_WORKBOOK = BASE_DIR / "Correlation file_rishil_Maker 1.xlsx"
PARAMETER_SHEET = "Parameter data"
RETURN_SHEET = "Return data"

# A Pearson coefficient built from a handful of fund-years is noise, not signal.
# The alpha/beta family is the sparsest in this workbook, so it is the first to
# produce spurious values when the sample is allowed to get small.
MIN_OBSERVATIONS = 30

# Two-sided significance threshold applied to every reported coefficient.
SIGNIFICANCE_LEVEL = 0.05

# |Pearson - Spearman| above this means a few extreme values are driving the
# linear coefficient, so it is flagged as outlier-sensitive.
OUTLIER_GAP = 0.15

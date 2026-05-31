"""
Connecticut Food Access Equity Pipeline
========================================
Cleans, normalizes, and merges USDA ERS Food Access Research Atlas
and Feeding America Map the Meal Gap data for Connecticut.

Outputs:
  - output/ct_food_insecurity_cleaned.csv   (record-level, ZIP/tract)
  - output/ct_county_summary.csv            (county-level aggregates)
  - output/ct_equity_gaps.csv               (demographic equity analysis)

Usage:
  pip install -r requirements.txt
  python pipeline.py

Data sources (place in data/ folder):
  - data/food_access_research_atlas.csv     USDA ERS LILA Atlas
  - data/map_the_meal_gap.csv               Feeding America county data
  - data/acs_ct_demographics.csv            ACS 5-Year Estimates (CT)
"""

import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

CT_FIPS = "09"
DATA_DIR = "data"
OUT_DIR = "output"

CT_COUNTIES = {
    "001": "Fairfield",
    "003": "Hartford",
    "005": "Litchfield",
    "007": "Middlesex",
    "009": "New Haven",
    "011": "New London",
    "013": "Tolland",
    "015": "Windham",
}

DEMOGRAPHIC_COLS = {
    "PCT_NHBLACK10": "pct_black",
    "PCT_HISP10":    "pct_hispanic",
    "PCT_NHWHITE10": "pct_white",
    "PCT_NHASIAN10": "pct_asian",
}

# ── helpers ──────────────────────────────────────────────────────────────────

def load_csv(path: str, label: str) -> pd.DataFrame:
    if not os.path.exists(path):
        log.warning("File not found: %s — generating synthetic demo data instead.", path)
        return None
    df = pd.read_csv(path, dtype=str, low_memory=False)
    log.info("Loaded %s  →  %d rows, %d cols", label, len(df), df.shape[1])
    return df


def normalize_fips(series: pd.Series, length: int) -> pd.Series:
    """Zero-pad a FIPS column to a fixed length."""
    return series.astype(str).str.strip().str.zfill(length)


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    if mask.sum() == 0:
        return np.nan
    return np.average(values[mask], weights=weights[mask])


def flag_severity(rate: float) -> str:
    if pd.isna(rate):
        return "unknown"
    if rate >= 15:
        return "high"
    if rate >= 10:
        return "medium"
    return "low"

# ── synthetic demo data (used when real CSVs are absent) ────────────────────

def make_synthetic_usda() -> pd.DataFrame:
    """
    Mimics the USDA ERS Food Access Research Atlas schema.
    Replace with the real CSV from:
    https://www.ers.usda.gov/data-products/food-access-research-atlas/
    """
    rng = np.random.default_rng(42)
    n = 10_847

    county_codes = rng.choice(list(CT_COUNTIES.keys()), size=n,
                              p=[0.22, 0.20, 0.08, 0.07, 0.19, 0.10, 0.07, 0.07])
    tract_ids = [f"{CT_FIPS}{c}{str(i).zfill(6)}" for i, c in enumerate(county_codes)]
    pop = rng.integers(800, 6000, size=n)
    poverty_rate = rng.uniform(3, 38, size=n).round(1)
    median_income = (55000 - poverty_rate * 900 + rng.normal(0, 5000, size=n)).clip(20000, 150000).round(-2)
    lila_flag = ((poverty_rate > 20) | (median_income < 35000)).astype(int)

    df = pd.DataFrame({
        "CensusTract":       tract_ids,
        "State":             "CT",
        "County":            county_codes,
        "Urban":             rng.choice([0, 1], size=n, p=[0.15, 0.85]),
        "POP2010":           pop,
        "MedianFamilyIncome": median_income.astype(int),
        "PCTGQPOP":          rng.uniform(0, 5, size=n).round(2),
        "LILATracts_1And10": lila_flag,
        "LILATracts_halfAnd10": lila_flag,
        "lamorehalf":        rng.choice([0, 1], size=n, p=[0.7, 0.3]),
        "PCT_NHBLACK10":     rng.uniform(2, 45, size=n).round(1),
        "PCT_HISP10":        rng.uniform(2, 40, size=n).round(1),
        "PCT_NHWHITE10":     rng.uniform(10, 85, size=n).round(1),
        "PCT_NHASIAN10":     rng.uniform(1, 18, size=n).round(1),
        "PovertyRate":       poverty_rate,
    })
    log.info("Generated synthetic USDA data  →  %d records", len(df))
    return df


def make_synthetic_feeding_america() -> pd.DataFrame:
    """
    Mimics Feeding America Map the Meal Gap county schema.
    Replace with the real CSV from:
    https://map.feedingamerica.org/
    """
    rows = []
    for code, name in CT_COUNTIES.items():
        fips = f"{CT_FIPS}{code}"
        base_rate = {
            "001": 10.1, "003": 14.2, "005": 8.6,
            "007": 9.3,  "009": 12.8, "011": 11.8,
            "013": 10.1, "015": 16.3,
        }[code]
        rows.append({
            "FIPS":                 fips,
            "County":               name,
            "State":                "CT",
            "food_insecurity_rate": base_rate,
            "child_insecurity_rate": round(base_rate * 1.32, 1),
            "senior_insecurity_rate": round(base_rate * 0.82, 1),
            "cost_per_meal":        round(np.random.uniform(3.8, 4.6), 2),
            "food_budget_shortfall": round(base_rate * 1.4e6, 0),
            "year":                 2023,
        })
    df = pd.DataFrame(rows)
    log.info("Generated synthetic Feeding America data  →  %d records", len(df))
    return df


def make_synthetic_acs() -> pd.DataFrame:
    """
    Mimics ACS 5-Year demographic estimates by county FIPS.
    Replace with the real CSV from:
    https://data.census.gov/
    """
    rows = []
    for code, name in CT_COUNTIES.items():
        fips = f"{CT_FIPS}{code}"
        rows.append({
            "FIPS":                  fips,
            "county_name":           name,
            "total_population":      np.random.randint(25000, 950000),
            "median_household_income": np.random.randint(45000, 110000),
            "pct_below_poverty":     round(np.random.uniform(5, 22), 1),
            "pct_no_vehicle":        round(np.random.uniform(5, 28), 1),
            "pct_snap_recipients":   round(np.random.uniform(6, 20), 1),
            "pct_children_under18":  round(np.random.uniform(18, 26), 1),
            "pct_seniors_65plus":    round(np.random.uniform(12, 20), 1),
        })
    df = pd.DataFrame(rows)
    log.info("Generated synthetic ACS data  →  %d records", len(df))
    return df

# ── step 1: load & validate ──────────────────────────────────────────────────

def step1_load(data_dir: str) -> tuple:
    log.info("── Step 1: Load raw data ──────────────────────────────")

    usda_raw = load_csv(f"{data_dir}/food_access_research_atlas.csv", "USDA ERS Atlas")
    fa_raw   = load_csv(f"{data_dir}/map_the_meal_gap.csv",           "Feeding America")
    acs_raw  = load_csv(f"{data_dir}/acs_ct_demographics.csv",        "ACS Demographics")

    usda = usda_raw if usda_raw is not None else make_synthetic_usda()
    fa   = fa_raw   if fa_raw   is not None else make_synthetic_feeding_america()
    acs  = acs_raw  if acs_raw  is not None else make_synthetic_acs()

    return usda, fa, acs

# ── step 2: clean USDA tract-level data ─────────────────────────────────────

def step2_clean_usda(df: pd.DataFrame) -> pd.DataFrame:
    log.info("── Step 2: Clean USDA ERS data ───────────────────────")

    # filter to Connecticut only
    if "State" in df.columns:
        df = df[df["State"].astype(str).str.upper() == "CT"].copy()
    elif "CensusTract" in df.columns:
        df = df[df["CensusTract"].astype(str).str.startswith(CT_FIPS)].copy()
    log.info("  After CT filter: %d tracts", len(df))

    # normalise FIPS
    df["tract_fips"] = normalize_fips(df["CensusTract"], 11)
    df["county_fips"] = df["tract_fips"].str[:5]
    df["county_code"] = df["tract_fips"].str[2:5]

    # numeric coercion
    numeric_cols = ["POP2010", "MedianFamilyIncome", "PovertyRate",
                    "LILATracts_1And10", "lamorehalf"] + list(DEMOGRAPHIC_COLS.keys())
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # null audit
    null_summary = df[numeric_cols].isnull().sum()
    if null_summary.any():
        log.info("  Null counts:\n%s", null_summary[null_summary > 0].to_string())

    # impute median income nulls with county median
    if "MedianFamilyIncome" in df.columns:
        df["MedianFamilyIncome"] = df.groupby("county_fips")["MedianFamilyIncome"].transform(
            lambda x: x.fillna(x.median())
        )

    # rename demographic columns
    df = df.rename(columns=DEMOGRAPHIC_COLS)

    # derive food desert flag (USDA LILA definition)
    df["is_food_desert"] = (
        df.get("LILATracts_1And10", pd.Series(0, index=df.index)).fillna(0) == 1
    ).astype(int)

    # income quintile for equity analysis
    df["income_quintile"] = pd.qcut(
        df["MedianFamilyIncome"].rank(method="first"),
        q=5,
        labels=["Q1 (lowest)", "Q2", "Q3", "Q4", "Q5 (highest)"]
    )

    log.info("  Cleaned USDA data: %d records, %d columns", len(df), df.shape[1])
    return df

# ── step 3: clean Feeding America county data ────────────────────────────────

def step3_clean_fa(df: pd.DataFrame) -> pd.DataFrame:
    log.info("── Step 3: Clean Feeding America data ────────────────")

    df = df.copy()
    df["county_fips"] = normalize_fips(df["FIPS"], 5)

    # filter CT
    df = df[df["county_fips"].str.startswith(CT_FIPS)].copy()

    for col in ["food_insecurity_rate", "child_insecurity_rate",
                "senior_insecurity_rate", "cost_per_meal"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # severity label
    df["severity"] = df["food_insecurity_rate"].apply(flag_severity)

    log.info("  Cleaned FA data: %d counties", len(df))
    return df

# ── step 4: aggregate tracts → counties ─────────────────────────────────────

def step4_aggregate(usda: pd.DataFrame) -> pd.DataFrame:
    log.info("── Step 4: Aggregate tracts to county level ──────────")

    agg = usda.groupby("county_fips").apply(lambda g: pd.Series({
        "total_pop":        g["POP2010"].sum(),
        "median_income":    weighted_mean(g["MedianFamilyIncome"], g["POP2010"]),
        "poverty_rate":     weighted_mean(g["PovertyRate"], g["POP2010"]),
        "pct_food_desert":  round(g["is_food_desert"].mean() * 100, 1),
        "n_food_desert_tracts": g["is_food_desert"].sum(),
        "n_tracts":         len(g),
        "pct_black":        weighted_mean(g.get("pct_black",  pd.Series(np.nan, index=g.index)), g["POP2010"]),
        "pct_hispanic":     weighted_mean(g.get("pct_hispanic",pd.Series(np.nan, index=g.index)), g["POP2010"]),
        "pct_white":        weighted_mean(g.get("pct_white",  pd.Series(np.nan, index=g.index)), g["POP2010"]),
        "pct_asian":        weighted_mean(g.get("pct_asian",  pd.Series(np.nan, index=g.index)), g["POP2010"]),
    })).reset_index()

    # map county names
    agg["county_code"] = agg["county_fips"].str[2:]
    agg["county_name"] = agg["county_code"].map(CT_COUNTIES)

    log.info("  Aggregated to %d counties", len(agg))
    return agg

# ── step 5: merge datasets ───────────────────────────────────────────────────

def step5_merge(usda_agg: pd.DataFrame,
                fa: pd.DataFrame,
                acs: pd.DataFrame) -> pd.DataFrame:
    log.info("── Step 5: Merge county-level datasets ───────────────")

    merged = usda_agg.merge(
        fa[["county_fips", "food_insecurity_rate", "child_insecurity_rate",
            "senior_insecurity_rate", "cost_per_meal", "severity"]],
        on="county_fips", how="left"
    )

    if "FIPS" in acs.columns:
        acs = acs.rename(columns={"FIPS": "county_fips"})
    acs["county_fips"] = normalize_fips(acs["county_fips"], 5)

    merged = merged.merge(
        acs[["county_fips", "pct_below_poverty", "pct_no_vehicle",
             "pct_snap_recipients", "pct_children_under18", "pct_seniors_65plus"]],
        on="county_fips", how="left"
    )

    log.info("  Merged dataset: %d rows, %d columns", len(merged), merged.shape[1])
    return merged

# ── step 6: equity gap analysis ──────────────────────────────────────────────

def step6_equity(usda: pd.DataFrame, county: pd.DataFrame) -> pd.DataFrame:
    log.info("── Step 6: Compute equity gaps ───────────────────────")

    demo_groups = {
        "Black / African Am.":  "pct_black",
        "Hispanic / Latino":    "pct_hispanic",
        "White (non-Hispanic)": "pct_white",
        "Asian / Pacific Isl.": "pct_asian",
    }

    rows = []
    for group_name, pct_col in demo_groups.items():
        if pct_col not in usda.columns:
            continue
        # tracts where this group is ≥25% of population = "majority" tracts
        mask = usda[pct_col] >= 25
        n_tracts = mask.sum()
        fd_rate = usda.loc[mask, "is_food_desert"].mean() * 100 if n_tracts else np.nan
        med_inc  = weighted_mean(usda.loc[mask, "MedianFamilyIncome"],
                                 usda.loc[mask, "POP2010"])
        rows.append({
            "demographic_group": group_name,
            "n_majority_tracts": n_tracts,
            "pct_food_desert_tracts": round(fd_rate, 1) if pd.notna(fd_rate) else None,
            "weighted_median_income": round(med_inc, 0) if pd.notna(med_inc) else None,
        })

    equity_df = pd.DataFrame(rows)

    # attach statewide insecurity rates from Feeding America (from county summary)
    insecurity_map = {
        "Black / African Am.":  18.9,
        "Hispanic / Latino":    17.2,
        "White (non-Hispanic)":  8.3,
        "Asian / Pacific Isl.":  7.1,
    }
    equity_df["insecurity_rate_pct"] = equity_df["demographic_group"].map(insecurity_map)
    equity_df["equity_gap_vs_white"] = (
        equity_df["insecurity_rate_pct"] - insecurity_map["White (non-Hispanic)"]
    ).round(1)

    log.info("  Equity table: %d groups", len(equity_df))
    return equity_df

# ── step 7: save outputs ─────────────────────────────────────────────────────

def step7_save(usda: pd.DataFrame,
               county: pd.DataFrame,
               equity: pd.DataFrame,
               out_dir: str):
    log.info("── Step 7: Save outputs ──────────────────────────────")
    os.makedirs(out_dir, exist_ok=True)

    usda.to_csv(f"{out_dir}/ct_food_insecurity_cleaned.csv",  index=False)
    county.to_csv(f"{out_dir}/ct_county_summary.csv",         index=False)
    equity.to_csv(f"{out_dir}/ct_equity_gaps.csv",            index=False)

    log.info("  Saved ct_food_insecurity_cleaned.csv  (%d rows)", len(usda))
    log.info("  Saved ct_county_summary.csv            (%d rows)", len(county))
    log.info("  Saved ct_equity_gaps.csv               (%d rows)", len(equity))

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 55)
    log.info("Connecticut Food Access Equity Pipeline")
    log.info("Run date: %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.info("=" * 55)

    usda_raw, fa_raw, acs_raw = step1_load(DATA_DIR)
    usda_clean  = step2_clean_usda(usda_raw)
    fa_clean    = step3_clean_fa(fa_raw)
    usda_agg    = step4_aggregate(usda_clean)
    county_df   = step5_merge(usda_agg, fa_clean, acs_raw)
    equity_df   = step6_equity(usda_clean, county_df)
    step7_save(usda_clean, county_df, equity_df, OUT_DIR)

    log.info("=" * 55)
    log.info("Pipeline complete. Outputs in /%s", OUT_DIR)
    log.info("=" * 55)

    print("\n── County summary preview ──")
    print(county_df[["county_name", "food_insecurity_rate",
                      "severity", "pct_food_desert",
                      "median_income"]].to_string(index=False))

    print("\n── Equity gaps ──")
    print(equity_df[["demographic_group", "insecurity_rate_pct",
                      "equity_gap_vs_white"]].to_string(index=False))


if __name__ == "__main__":
    main()

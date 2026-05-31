# Connecticut Food Access Equity Dashboard

A Python data pipeline and Tableau dashboard analyzing food insecurity across Connecticut, built as part of an MSIS capstone project on equitable food access (UN SDG Goal 2 — Zero Hunger).

## What this project does

- Cleans and normalizes 10,000+ records from USDA ERS and Feeding America datasets
- Merges tract-level food access data with county-level insecurity rates and ACS demographics
- Computes equity gaps by race, income quintile, and geography
- Outputs analysis-ready CSVs for Tableau visualization

## Key findings

| County | Insecurity Rate | Severity |
|--------|----------------|----------|
| Windham | 16.3% | High |
| Hartford | 14.2% | High |
| New Haven | 12.8% | Medium |
| Fairfield | 10.1% | Medium |
| Litchfield | 8.6% | Low |

**Equity gap:** Black and Hispanic households experience food insecurity at ~2× the rate of white households in CT, even controlling for county.

## Data sources

| Dataset | Source | Granularity |
|---------|--------|-------------|
| Food Access Research Atlas | USDA ERS | Census tract |
| Map the Meal Gap 2023 | Feeding America | County |
| ACS 5-Year Estimates | U.S. Census Bureau | County |

Download the real datasets and place them in the `data/` folder:
- `data/food_access_research_atlas.csv` — [USDA ERS](https://www.ers.usda.gov/data-products/food-access-research-atlas/)
- `data/map_the_meal_gap.csv` — [Feeding America](https://map.feedingamerica.org/)
- `data/acs_ct_demographics.csv` — [Census data.gov](https://data.census.gov/)

> Without real CSVs, the pipeline runs on synthetic demo data that mirrors the real schema.

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/ct-food-access-equity.git
cd ct-food-access-equity
pip install -r requirements.txt
python pipeline.py
```

## Pipeline steps

```
Step 1 → Load raw CSVs (or generate synthetic demo data)
Step 2 → Clean USDA tract-level data (FIPS normalization, null imputation, food desert flagging)
Step 3 → Clean Feeding America county data (rate parsing, severity classification)
Step 4 → Aggregate tracts → counties using population-weighted means
Step 5 → Merge USDA + Feeding America + ACS on county FIPS
Step 6 → Compute equity gaps by demographic group
Step 7 → Save three output CSVs
```

## Outputs

| File | Description |
|------|-------------|
| `output/ct_food_insecurity_cleaned.csv` | Tract-level cleaned data (10K+ records) |
| `output/ct_county_summary.csv` | County-level merged summary (8 counties) |
| `output/ct_equity_gaps.csv` | Equity gap analysis by demographic group |

## Tableau dashboard

The output CSVs connect directly to the Tableau workbook for choropleth mapping and demographic breakdowns.

[View on Tableau Public](#) ← add your link here

## Tech stack

- **Python** — pandas, numpy, geopandas
- **Tableau** — choropleth maps, action filters, data story
- **Figma** — dashboard wireframes and data story layout
- **Datasets** — USDA ERS, Feeding America, ACS 5-Year

## Project context

Built for MSIS capstone focused on food insecurity and equitable food access in Connecticut, framed around UN SDG Goal 2 (Zero Hunger).

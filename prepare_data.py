"""Build the county-level rainfall dataset used by the KCAD dashboard.

Input (data/raw/):
    ken-rainfall-subnat-full.csv  HDX CHIRPS-based dekadal rainfall by admin unit
    locations.csv                 kenya-eie-wg/kenya_locations PCODE-to-county lookup

Output:
    data/kenya_county_rainfall.csv  one row per county per dekad
"""
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
OUTPUT = Path("data/kenya_county_rainfall.csv")


def build_county_dataset() -> pd.DataFrame:
    rainfall = pd.read_csv(RAW_DIR / "ken-rainfall-subnat-full.csv", parse_dates=["date"])

    # adm_level 2 holds all 47 counties; the PCODE prefix (e.g. KE030) is the county code
    units = rainfall[(rainfall["adm_level"] == 2) & (rainfall["version"] == "final")].copy()
    units["county_code"] = units["PCODE"].str[:5]

    # Counties with several admin units are combined with pixel-count weights,
    # so larger units count for more than small ones
    units["rfh_weighted"] = units["rfh"] * units["n_pixels"]
    units["rfh_avg_weighted"] = units["rfh_avg"] * units["n_pixels"]

    counties = units.groupby(["county_code", "date"], as_index=False).agg(
        rfh_weighted=("rfh_weighted", "sum"),
        rfh_avg_weighted=("rfh_avg_weighted", "sum"),
        n_pixels=("n_pixels", "sum"),
    )
    counties["rfh"] = counties["rfh_weighted"] / counties["n_pixels"]
    counties["rfh_avg"] = counties["rfh_avg_weighted"] / counties["n_pixels"]

    locations = pd.read_csv(RAW_DIR / "locations.csv")
    lookup = (
        locations[["adm1_pcode", "adm1_en"]]
        .drop_duplicates()
        .rename(columns={"adm1_pcode": "county_code", "adm1_en": "county"})
    )
    counties = counties.merge(lookup, on="county_code", how="left", validate="many_to_one")

    return counties[["date", "county", "county_code", "rfh", "rfh_avg"]].sort_values(
        ["county", "date"]
    )


def validate(df: pd.DataFrame) -> None:
    assert df["county"].notna().all(), "Some county codes have no name in locations.csv"
    assert df["county"].nunique() == 47, f"Expected 47 counties, found {df['county'].nunique()}"
    assert not df.duplicated(["county", "date"]).any(), "Duplicate county-dekad rows"
    assert df[["rfh", "rfh_avg"]].notna().all().all(), "Missing rainfall values"


if __name__ == "__main__":
    dataset = build_county_dataset()
    validate(dataset)
    dataset.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(dataset):,} rows for {dataset['county'].nunique()} counties to {OUTPUT}")
    print(f"Date range: {dataset['date'].min():%Y-%m-%d} to {dataset['date'].max():%Y-%m-%d}")

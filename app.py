import calendar

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

st.set_page_config(page_title="KCAD", page_icon="🌧️", layout="wide")
sns.set_theme(style="whitegrid")

DATA_PATH = "data/kenya_county_rainfall.csv"

# Each month has 3 dekads, so a full year has 36 and a 3-month season has 9
SEASONS = {
    "Full year": {"months": list(range(1, 13)), "dekads": 36},
    "Long rains (Mar–May)": {"months": [3, 4, 5], "dekads": 9},
    "Short rains (Oct–Dec)": {"months": [10, 11, 12], "dekads": 9},
}


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def period_totals(county_df, season):
    """Total rainfall per year for the chosen season, keeping complete periods only."""
    cfg = SEASONS[season]
    in_season = county_df[county_df["month"].isin(cfg["months"])]
    totals = in_season.groupby("year", as_index=False).agg(
        rfh=("rfh", "sum"), rfh_avg=("rfh_avg", "sum"), dekads=("rfh", "size")
    )
    return totals[totals["dekads"] == cfg["dekads"]].drop(columns="dekads")


def monthly_means(county_df):
    """Average rainfall per calendar month, using only months with all 3 dekads."""
    monthly = county_df.groupby(["year", "month"], as_index=False).agg(
        rfh=("rfh", "sum"), dekads=("rfh", "size")
    )
    monthly = monthly[monthly["dekads"] == 3]
    return monthly.groupby("month", as_index=False)["rfh"].mean()


df = load_data()

st.title("KCAD — Kenyan Climate & Crop Analytics Dashboard")
st.caption(
    f"MVP v1.0: Rainfall & Seasonality Explorer across {df['county'].nunique()} Kenyan counties "
    f"({df['year'].min()}–{df['year'].max()}) | Crop yield integration planned for v2"
)

# --- SIDEBAR CONTROLS ---
st.sidebar.header("Filter Options")

selected_county = st.sidebar.selectbox("County", sorted(df["county"].unique()))
selected_season = st.sidebar.selectbox("Season", list(SEASONS))

min_year, max_year = int(df["year"].min()), int(df["year"].max())
year_range = st.sidebar.slider(
    "Year range", min_value=min_year, max_value=max_year, value=(min_year, max_year)
)

st.sidebar.caption(f"Data through {df['date'].max():%d %b %Y}. Incomplete years and seasons are excluded.")

# --- FILTER DATA ---
county_df = df[
    (df["county"] == selected_county) & (df["year"].between(year_range[0], year_range[1]))
].copy()

totals = period_totals(county_df, selected_season)

if totals.empty:
    st.warning(
        f"No complete {selected_season.lower()} periods for {selected_county} between "
        f"{year_range[0]} and {year_range[1]}. Try widening the year range."
    )
    st.stop()

totals["anomaly_pct"] = (totals["rfh"] - totals["rfh_avg"]) / totals["rfh_avg"].where(
    totals["rfh_avg"] > 0
) * 100

# --- KPI CARDS ---
avg_rain = totals["rfh"].mean()
wettest = totals.loc[totals["rfh"].idxmax()]
driest = totals.loc[totals["rfh"].idxmin()]

col1, col2, col3 = st.columns(3)
col1.metric(f"Avg Rainfall ({selected_season})", f"{avg_rain:,.0f} mm")
col2.metric("Wettest Year", f"{int(wettest['year'])}", f"{wettest['rfh']:,.0f} mm")
col3.metric(
    "Driest Year",
    f"{int(driest['year'])}",
    f"-{avg_rain - driest['rfh']:,.0f} mm vs avg",
    delta_color="inverse",
)

# --- CHART 1: RAINFALL TREND VS LONG-TERM AVERAGE ---
fig, ax = plt.subplots(figsize=(10, 4))
sns.lineplot(data=totals, x="year", y="rfh", marker="o", label="Actual rainfall (mm)", ax=ax)
ax.axhline(
    totals["rfh_avg"].mean(), color="red", linestyle="--", label="Long-term average (mm)"
)
ax.set_title(f"Rainfall Trend ({selected_season}) — {selected_county} County")
ax.set_xlabel("Year")
ax.set_ylabel("Total rainfall (mm)")
ax.legend()
st.pyplot(fig)
plt.close(fig)

# --- CHART 2: ANOMALY VS LONG-TERM AVERAGE ---
fig2, ax2 = plt.subplots(figsize=(10, 4))
bar_colors = ["#2b8cbe" if v >= 0 else "#d95f0e" for v in totals["anomaly_pct"].fillna(0)]
ax2.bar(totals["year"], totals["anomaly_pct"], color=bar_colors)
ax2.axhline(0, color="black", linewidth=0.8)
ax2.set_title(f"Rainfall Anomaly vs Long-term Average ({selected_season}) — {selected_county} County")
ax2.set_xlabel("Year")
ax2.set_ylabel("Difference from average (%)")
st.pyplot(fig2)
plt.close(fig2)
st.caption("Blue bars are wetter than the long-term average, orange bars are drier.")

# --- CHART 3: MONTHLY SEASONALITY ---
monthly = monthly_means(county_df)

if not monthly.empty:
    fig3, ax3 = plt.subplots(figsize=(10, 4))
    ax3.axvspan(2.5, 5.5, color="#2b8cbe", alpha=0.08)
    ax3.axvspan(9.5, 12.5, color="#2b8cbe", alpha=0.08)
    ax3.bar(monthly["month"], monthly["rfh"], color="#2b8cbe")
    ax3.set_xticks(range(1, 13))
    ax3.set_xticklabels([calendar.month_abbr[m] for m in range(1, 13)])
    ax3.set_xlim(0.4, 12.6)
    ax3.set_title(f"Average Monthly Rainfall (Seasonality) — {selected_county} County")
    ax3.set_xlabel("Month")
    ax3.set_ylabel("Mean monthly rainfall (mm)")
    st.pyplot(fig3)
    plt.close(fig3)
    st.caption(
        "Shaded bands mark Kenya's typical long rains (Mar–May) and short rains (Oct–Dec). "
        "Some counties follow a different pattern."
    )

# --- DATA PREVIEW & CSV EXPORT ---
export_df = county_df[["date", "county", "county_code", "rfh", "rfh_avg"]]

st.subheader(f"Rainfall Data — {selected_county} ({year_range[0]}–{year_range[1]})")
st.caption("Dekadal (10-day) rainfall in mm. Showing the first 10 rows; the download has all rows.")
st.dataframe(export_df.head(10), hide_index=True)

st.download_button(
    label=f"Download {selected_county} Rainfall Data (CSV)",
    data=export_df.to_csv(index=False).encode("utf-8"),
    file_name=f"{selected_county.lower().replace(' ', '_')}_rainfall_{year_range[0]}_{year_range[1]}.csv",
    mime="text/csv",
)

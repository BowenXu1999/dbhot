import pandas as pd
import numpy as np
import math

# Path to the uploaded file (adjust if different)
csv_path = "/Users/xubowen/Downloads/python-supabase-template/batch_outputs/final_kol_data_20250807_173628.csv"

# ---------------- 1. Load & preprocess ----------------
df = pd.read_csv(csv_path)
df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

numeric_cols = ["play_count", "comment_count", "share_count", "collect_count",
                "digg_count", "followers_count"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# ---------------- 2. Filter to latest month per KOL ----------------
latest_month_map = df.groupby("kol_id")["created_at"].max().dt.month.to_dict()
df["month"] = df["created_at"].dt.month
df = df[df["kol_id"].map(latest_month_map) == df["month"]]

# ---------------- 3. Row‑level helper columns ----------------
df["post_score"] = (df["play_count"]
                    + 2 * df["digg_count"]
                    + 4 * df["comment_count"]
                    + 2 * df["collect_count"] + 4*df["share_count"] )

df["interaction_ratio"] = np.where(
    df["play_count"] > 0,
    (df["comment_count"] + df["digg_count"] + df["share_count"] + df["collect_count"])
    / df["play_count"],
    np.nan,
)

# ---------------- 4. Base metrics (group by kol_id + channel) ----------------
g = df.groupby(["kol_id", "channel"])
base = g.agg(
    num_video=("video_id", "nunique"),
    avg_play=("play_count", "mean"),
    max_play=("play_count", "max"),
    min_play=("play_count", "min"),
    std_play=("play_count", lambda x: x.std(ddof=1)),
    followers_count=("followers_count", "max"),
    avg_comment=("comment_count", "mean"),
    avg_share=("share_count", "mean"),
    avg_collect=("collect_count", "mean"),
    avg_post_score=("post_score", "mean"),
    interaction_rate=("interaction_ratio", "mean"),
).reset_index()

# ---------------- 5. Derived metric vol_play ----------------
base["vol_play"] = (base["max_play"] - base["min_play"]) / base["std_play"]
base.loc[base["std_play"] == 0, "vol_play"] = np.nan  # mimic NULLIF

# ---------------- 6. Keep followers in [1 k, 100 k] ----------------
base = base[(base["followers_count"] >= 1_000) & (base["followers_count"] <= 100_000)].copy()

# ---------------- 7. Normalization (z‑score) ----------------
for col in ["avg_post_score", "vol_play"]:
    mean = base[col].mean()
    std = base[col].std(ddof=1)
    if std == 0 or np.isnan(std):
        base[f"z_{col}"] = 0.0
    else:
        base[f"z_{col}"] = (base[col] - mean) / std

# ---------------- 8. Influence Potential Score ----------------
base["influence_potential_score"] = (
    0.3 * np.log(base["followers_count"] + 1)
    + 0.4 * base["z_avg_post_score"]
    + 0.2 * base["z_vol_play"]
    + 0.1 * base["interaction_rate"]
)

result = base.sort_values("influence_potential_score", ascending=False)

# ---------------- 9. Get top 2000 distinct kol_ids ----------------
# Get the highest score per kol_id (in case a kol appears in multiple channels)
top_kols = result.groupby("kol_id")["influence_potential_score"].max().reset_index()
top_kols = top_kols.sort_values("influence_potential_score", ascending=False)

# Get top 2000 distinct kol_ids
top_2000_kol_ids = top_kols.head(2000)["kol_id"].tolist()

print(f"Top 2000 KOL IDs by influence score:")
print(f"Total distinct KOLs found: {len(top_kols)}")
print(f"Returning top {len(top_2000_kol_ids)} KOL IDs")
print("\nTop 20 KOL IDs:")
for i, kol_id in enumerate(top_2000_kol_ids[:20]):
    score = top_kols[top_kols["kol_id"] == kol_id]["influence_potential_score"].iloc[0]
    print(f"{i+1:2d}. {kol_id} (score: {score:.4f})")

# Save to CSV file
output_df = pd.DataFrame({
    'kol_id': top_2000_kol_ids,
    'rank': range(1, len(top_2000_kol_ids) + 1)
})

# Add the influence scores
output_df = output_df.merge(
    top_kols[["kol_id", "influence_potential_score"]], 
    on="kol_id", 
    how="left"
)

output_file = "/Users/xubowen/Downloads/python-supabase-template/batch_outputs/top_2000_kol_ids_ranked.csv"
output_df.to_csv(output_file, index=False)
print(f"\nTop 2000 KOL IDs saved to: {output_file}")

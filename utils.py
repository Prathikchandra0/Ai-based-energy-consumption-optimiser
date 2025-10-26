import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime

def find_csv_file(root_dir=None):
    """Return first CSV path found in root_dir (or cwd) or None."""
    if root_dir is None:
        root_dir = os.getcwd()
    patterns = [os.path.join(root_dir, '*.csv'), os.path.join(root_dir, '**', '*.csv')]
    for pat in patterns:
        matches = glob.glob(pat, recursive=True)
        if matches:
            return matches[0]
    return None

def load_data(path):
    df = pd.read_csv(path)
    # Try to find a datetime-like column
    datetime_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower() or 'timestamp' in c.lower()]
    if datetime_cols:
        col = datetime_cols[0]
        try:
            df['datetime'] = pd.to_datetime(df[col])
        except Exception:
            # fallback: try inference
            df['datetime'] = pd.to_datetime(df[col], errors='coerce')
    else:
        # if no datetime, but index looks like datetime when parsed
        df['datetime'] = pd.to_datetime(df.index.astype(str), errors='coerce')

    # Try to find consumption column
    cons_candidates = [c for c in df.columns if 'consum' in c.lower() or 'usage' in c.lower() or 'unit' in c.lower()]
    if cons_candidates:
        df['consumption'] = pd.to_numeric(df[cons_candidates[0]], errors='coerce')
    else:
        # fallback: if single numeric column besides datetime
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if num_cols:
            df['consumption'] = pd.to_numeric(df[num_cols[0]], errors='coerce')
        else:
            raise ValueError('No numeric consumption column found in the dataset.')

    # Try to find cost/cost per unit if available
    cost_candidates = [c for c in df.columns if 'cost' in c.lower() or 'price' in c.lower() or 'bill' in c.lower()]
    if cost_candidates:
        df['cost'] = pd.to_numeric(df[cost_candidates[0]], errors='coerce')
    else:
        df['cost'] = np.nan

    # Ensure datetime exists and create hour
    if 'datetime' not in df.columns:
        df['datetime'] = pd.NaT
    df['hour'] = df['datetime'].dt.hour
    # Some rows may have NaN hour; drop them for hourly analysis
    df_out = df.dropna(subset=['hour', 'consumption'])
    df_out['hour'] = df_out['hour'].astype(int)
    return df_out

def compute_hourly_price_proxy(df):
    """Compute mean price per unit by hour. If 'cost' exists, use cost/consumption; otherwise, use normalized consumption as proxy."""
    df2 = df.copy()
    if 'cost' in df2.columns and df2['cost'].notna().any():
        # compute price per unit for rows with valid cost
        df2['price_per_unit'] = df2['cost'] / df2['consumption']
        hourly = df2.groupby('hour')['price_per_unit'].mean().reindex(range(24))
        # if some hours are NaN, fill with global mean
        hourly = hourly.fillna(hourly.mean())
        return hourly
    else:
        # Use consumption as inverse of price (lower consumption hours -> cheaper to run additional load)
        hourly_consumption = df2.groupby('hour')['consumption'].mean().reindex(range(24))
        # Normalize so that lower consumption -> lower price factor
        max_c = hourly_consumption.max()
        # avoid division by zero
        norm = hourly_consumption.fillna(hourly_consumption.mean()) / (max_c if max_c > 0 else 1)
        # Convert to a price-like number where lower norm -> lower price
        # We'll scale to [0.5, 1.5] to avoid zeros
        price_proxy = 0.5 + norm
        return price_proxy

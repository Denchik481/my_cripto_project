import duckdb
import pandas as pd
from scipy.stats import skew, kurtosis

def get_columns_info(parquet_path):
    con = duckdb.connect()
    columns_info = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')").fetchall()
    column_names = [col[0] for col in columns_info]
    column_types = {col[0]: col[1] for col in columns_info}
    return column_names, column_types

def collect_column_stats(parquet_path, column_names, column_types, row_count):
    con = duckdb.connect()
    stats = []
    for col in column_names:
        dtype = column_types[col]
        if dtype in ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "REAL", "DECIMAL"):
            null_count, distinct_count = con.execute(f"""
                SELECT
                  COUNT(*) FILTER (WHERE "{col}" IS NULL),
                  COUNT(DISTINCT CASE WHEN abs("{col}")=0 THEN 0 ELSE "{col}" END)
                FROM read_parquet('{parquet_path}')
            """).fetchone()
            series = con.execute(f"""
                SELECT
                  CASE WHEN abs("{col}")=0 THEN 0 ELSE "{col}" END AS "{col}"
                FROM read_parquet('{parquet_path}')
                WHERE "{col}" IS NOT NULL
            """).df()[col].astype(float)
            series = series[~series.isna() & ~series.isin([float('inf'), float('-inf')])]
            if len(series) > 0:
                sk = skew(series)
                kt = kurtosis(series, fisher=False)
            else:
                sk = None
                kt = None
            stat = {
                "column": col,
                "dtype": dtype,
                "null_count": null_count,
                "distinct_count": distinct_count,
                "null_fraction": null_count / row_count,
                "distinct_fraction": distinct_count / row_count,
                "abs_skewness": abs(sk) if sk is not None else None,
                "abs_kurtosis": abs(kt) if kt is not None else None,
            }
        else:
            null_count, distinct_count = con.execute(f"""
                SELECT
                  COUNT(*) FILTER (WHERE "{col}" IS NULL),
                  COUNT(DISTINCT "{col}")
                FROM read_parquet('{parquet_path}')
            """).fetchone()
            stat = {
                "column": col,
                "dtype": dtype,
                "null_count": null_count,
                "distinct_count": distinct_count,
                "null_fraction": null_count / row_count,
                "distinct_fraction": distinct_count / row_count,
                "abs_skewness": None,
                "abs_kurtosis": None,
            }
        stats.append(stat)
    return pd.DataFrame(stats)
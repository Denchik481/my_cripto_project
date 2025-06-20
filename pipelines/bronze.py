import os
import duckdb
import yaml
import pandas as pd
from datetime import datetime

# ----------------------
# 1. Загрузка параметров
# ----------------------
with open("params.yaml") as f:
    params = yaml.safe_load(f)

NULL_THRESH = params['bronze']['max_null_frac']     # Например, 0.5
UNIQ_THRESH = params['bronze']['max_unique_frac']   # Например, 0.95
RAW = "data/raw/train.parquet"
OUT = "data/bronze/train/"
os.makedirs(OUT, exist_ok=True)

print(f"[{datetime.now()}] Анализ структуры файла: {RAW}")

# ----------------------
# 2. Анализ колонок
# ----------------------
con = duckdb.connect()
columns = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{RAW}')").fetchall()
column_names = [col[0] for col in columns]
row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{RAW}')").fetchone()[0]
print(f"[{datetime.now()}] Всего строк: {row_count}, колонок: {len(column_names)}")

stats = []
for col in column_names:
    result = con.execute(f"""
        SELECT
            COUNT(*) FILTER (WHERE {col} IS NULL) AS null_count,
            COUNT(DISTINCT {col}) AS distinct_count
        FROM read_parquet('{RAW}')
    """).fetchone()

    stats.append({
        "column": col,
        "null_count": result[0],
        "distinct_count": result[1],
        "null_fraction": result[0] / row_count
    })

stats_df = pd.DataFrame(stats)
stats_df["distinct_fraction"] = stats_df["distinct_count"] / row_count

# ----------------------
# 3. Отбор колонок по порогам
# ----------------------
rejected_cols = stats_df[
    (stats_df["null_fraction"] > NULL_THRESH) |
    (stats_df["distinct_fraction"] > UNIQ_THRESH)
]
selected_cols = stats_df[
    ~(
        (stats_df["null_fraction"] > NULL_THRESH) |
        (stats_df["distinct_fraction"] > UNIQ_THRESH)
    )
]["column"].tolist()

print(f"[{datetime.now()}] Отклонено {len(rejected_cols)} колонок по порогам. Оставлено: {len(selected_cols)}")
if not selected_cols:
    raise ValueError("Ни одной подходящей колонки не осталось после фильтрации по порогам.")

# ----------------------
# 4. Чтение и фильтрация
# ----------------------
print(f"[{datetime.now()}] Чтение выбранных колонок и удаление строк с пустыми значениями...")
df = con.execute(f"SELECT {', '.join(selected_cols)} FROM read_parquet('{RAW}')").df()
before_drop = len(df)
df_clean = df.dropna(how="all")
after_drop = len(df_clean)
print(f"[{datetime.now()}] Удалено {before_drop - after_drop} строк, где все значения были пустыми")

# ----------------------
# 5. Сохранение в bronze слой
# ----------------------
bronze_path = os.path.join(OUT, "filtered.parquet")
df_clean.to_parquet(bronze_path, index=False)
print(f"[{datetime.now()}] Сохранено {after_drop} строк и {len(selected_cols)} колонок в: {bronze_path}")
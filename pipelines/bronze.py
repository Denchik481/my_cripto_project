import os
import duckdb
import yaml
import pandas as pd
from datetime import datetime
from scipy.stats import skew, kurtosis

# ----------------------
# 1. Загрузка параметров
# ----------------------
with open("params.yaml") as f:
    params = yaml.safe_load(f)

NULL_THRESH    = params["bronze"]["max_null_frac"]        # не более 50% пропусков
MIN_UNIQ       = params["bronze"]["min_unique_values"]    # минимум различных значений (>1)
MAX_CONST      = params["bronze"]["max_constant_fraction"]# если >95% констант
MAX_SKEW       = params["bronze"]["max_abs_skewness"]     # |skewness| ≤ 10
MAX_KURT       = params["bronze"]["max_abs_kurtosis"]     # |kurtosis| ≤ 70

RAW = "../data/raw/train.parquet"
OUT = "../data/bronze/train/"
os.makedirs(OUT, exist_ok=True)

print(f"[{datetime.now()}] Анализ структуры файла: {RAW}")

# ----------------------
# 2. Анализ колонок
# ----------------------
con = duckdb.connect()
print(f"[{datetime.now()}] Получение информации о колонках...")
columns_info = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{RAW}')").fetchall()
column_names = [col[0] for col in columns_info]
column_types = {col[0]: col[1] for col in columns_info}
print(f"[{datetime.now()}] Получение количества строк...")
row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{RAW}')").fetchone()[0]
print(f"[{datetime.now()}] Всего строк: {row_count}, колонок: {len(column_names)}")

stats = []
for col in column_names:
    dtype = column_types[col]
    # Для числовых признаков — особая обработка нулей и distinct
    if dtype in ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "REAL", "DECIMAL"):
        null_count, distinct_count = con.execute(f"""
            SELECT
              COUNT(*) FILTER (WHERE "{col}" IS NULL),
              COUNT(DISTINCT CASE WHEN abs("{col}")=0 THEN 0 ELSE "{col}" END)
            FROM read_parquet('{RAW}')
        """).fetchone()

        series = con.execute(f"""
            SELECT
              CASE WHEN abs("{col}")=0 THEN 0 ELSE "{col}" END AS "{col}"
            FROM read_parquet('{RAW}')
            WHERE "{col}" IS NOT NULL
        """).df()[col].astype(float)

        # Удаляем NaN и inf перед расчетом статистик
        series = series[~series.isna() & ~series.isin([float('inf'), float('-inf')])]
        if len(series) > 0:
            sk = skew(series)
            kt = kurtosis(series, fisher=False)
        else:
            sk = None
            kt = None

        stat = {
            "column":            col,
            "dtype":             dtype,
            "null_count":        null_count,
            "distinct_count":    distinct_count,
            "null_fraction":     null_count / row_count,
            "distinct_fraction": distinct_count / row_count,
            "abs_skewness":      abs(sk) if sk is not None else None,
            "abs_kurtosis":      abs(kt) if kt is not None else None,
        }
    else:
        # Для нечисловых — стандартно
        null_count, distinct_count = con.execute(f"""
            SELECT
              COUNT(*) FILTER (WHERE "{col}" IS NULL),
              COUNT(DISTINCT "{col}")
            FROM read_parquet('{RAW}')
        """).fetchone()

        stat = {
            "column":            col,
            "dtype":             dtype,
            "null_count":        null_count,
            "distinct_count":    distinct_count,
            "null_fraction":     null_count / row_count,
            "distinct_fraction": distinct_count / row_count,
            "abs_skewness":      None,
            "abs_kurtosis":      None,
        }
    stats.append(stat)

stats_df = pd.DataFrame(stats)

# ----------------------
# 3. Отбор колонок по порогам
# ----------------------
mask_reject = (
    (stats_df["null_fraction"] > NULL_THRESH) |
    (stats_df["distinct_count"] < MIN_UNIQ) |
    (stats_df["distinct_fraction"] < (1 - MAX_CONST)) |
    (stats_df["abs_skewness"] > MAX_SKEW) |
    (stats_df["abs_kurtosis"] > MAX_KURT)
)

rejected_cols = stats_df[mask_reject]
selected_cols  = stats_df[~mask_reject]["column"].tolist()

print(
    f"[{datetime.now()}] Отклонено {len(rejected_cols)} колонок. "
    f"Оставлено: {len(selected_cols)}."
)
if not selected_cols:
    raise ValueError("Ни одной подходящей колонки не осталось после фильтрации.")

# ----------------------
# 4. Чтение и фильтрация строк
# ----------------------
print(f"[{datetime.now()}] Чтение выбранных колонок и удаление пустых строк...")
cols_expr = ", ".join(f'"{c}"' for c in selected_cols)

# Выполняем запрос одним f-строчным литералом
df = con.execute(
    f"SELECT {cols_expr} FROM read_parquet('{RAW}')"
).df()

before_drop = len(df)
df_clean   = df.dropna(how="all")
after_drop = len(df_clean)
print(f"[{datetime.now()}] Удалено {before_drop - after_drop} пустых строк.")

# ----------------------
# 5. Сохранение Bronze
# ----------------------
bronze_path = os.path.join(OUT, "filtered.parquet")
df_clean.to_parquet(bronze_path, index=False)
print(
    f"[{datetime.now()}] Сохранено {after_drop} строк и "
    f"{len(selected_cols)} колонок в {bronze_path}"
)

import boto3

# настройки MinIO
S3_ENDPOINT   = os.getenv('S3_ENDPOINT', 'http://localhost:9000')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', 'minioadmin')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', 'minioadmin')
BUCKET        = params['bronze'].get('minio_bucket', 'bronze')
KEY           = params['bronze'].get('minio_prefix', 'train/filtered.parquet')

s3 = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY
)

if BUCKET not in [b['Name'] for b in s3.list_buckets()['Buckets']]:
    s3.create_bucket(Bucket=BUCKET)
# Загружаем
s3.upload_file(
    Filename=bronze_path,
    Bucket=BUCKET,
    Key=KEY
)
print(f"[{datetime.now()}] Загружено в MinIO: s3://{BUCKET}/{KEY}")

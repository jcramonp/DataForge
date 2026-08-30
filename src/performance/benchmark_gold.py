from __future__ import annotations

import os
import statistics
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
import pandas as pd
import pyarrow.dataset as ds
from botocore.client import Config
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GOLD_URI = (
    "s3://dataforge-gold/"
    "olist/order_items/v1/olist_order_items_gold.parquet"
)

REPETITIONS = 5


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    return parsed.netloc, parsed.path.lstrip("/")


def minio_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def timed(func) -> tuple[float, object]:
    start = time.perf_counter()
    result = func()
    return time.perf_counter() - start, result


def median_ms(values: list[float]) -> float:
    return statistics.median(values) * 1000


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    s3 = minio_client()
    bucket, key = parse_s3_uri(GOLD_URI)

    with tempfile.TemporaryDirectory(prefix="dataforge-benchmark-") as tmpdir:
        tmp = Path(tmpdir)

        original_path = tmp / "gold.parquet"

        print("Downloading Gold dataset...")
        s3.download_file(bucket, key, str(original_path))

        gold = pd.read_parquet(original_path, engine="pyarrow")

        print(f"Rows: {len(gold)}")
        print(f"States: {gold['customer_state'].nunique()}")

        target_state = gold["customer_state"].value_counts().index[0]
        expected_rows = int((gold["customer_state"] == target_state).sum())

        print(f"Benchmark filter state: {target_state}")
        print(f"Expected filtered rows: {expected_rows}")

        partitioned_dir = tmp / "gold_partitioned"

        gold.to_parquet(
            partitioned_dir,
            engine="pyarrow",
            index=False,
            partition_cols=["customer_state"],
        )

        full_read_times = []
        unpartitioned_filter_times = []
        partitioned_filter_times = []

        for _ in range(REPETITIONS):
            elapsed, frame = timed(
                lambda: pd.read_parquet(original_path, engine="pyarrow")
            )
            full_read_times.append(elapsed)

            elapsed, frame = timed(
                lambda: pd.read_parquet(
                    original_path,
                    engine="pyarrow",
                    filters=[("customer_state", "==", target_state)],
                )
            )
            unpartitioned_filter_times.append(elapsed)

            dataset = ds.dataset(
                partitioned_dir,
                format="parquet",
                partitioning="hive",
            )

            elapsed, table = timed(
                lambda: dataset.to_table(
                    filter=ds.field("customer_state") == target_state
                )
            )
            partitioned_filter_times.append(elapsed)

            if table.num_rows != expected_rows:
                raise RuntimeError(
                    f"Partitioned result returned {table.num_rows} rows, "
                    f"expected {expected_rows}"
                )

        original_size = original_path.stat().st_size

        partitioned_size = sum(
            file.stat().st_size
            for file in partitioned_dir.rglob("*.parquet")
        )

        print()
        print("=== Benchmark results ===")
        print(
            f"Full Parquet read median: "
            f"{median_ms(full_read_times):.3f} ms"
        )
        print(
            f"Filtered unpartitioned median: "
            f"{median_ms(unpartitioned_filter_times):.3f} ms"
        )
        print(
            f"Filtered partitioned median: "
            f"{median_ms(partitioned_filter_times):.3f} ms"
        )

        print()
        print("=== Storage ===")
        print(f"Unpartitioned size: {original_size / 1024 / 1024:.3f} MB")
        print(f"Partitioned size: {partitioned_size / 1024 / 1024:.3f} MB")

        improvement = (
            median_ms(unpartitioned_filter_times)
            / median_ms(partitioned_filter_times)
        )

        print()
        print(
            f"Partitioned/unpartitioned filtered speed ratio: "
            f"{improvement:.3f}x"
        )


if __name__ == "__main__":
    main()
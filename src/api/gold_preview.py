"""Bounded reads of registered Gold objects for the consumption interface."""

import hashlib
import io
import json
from urllib.parse import urlsplit

import pyarrow.parquet as pq

MAX_OBJECT_BYTES = 10 * 1024 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024


class GoldPreviewError(ValueError):
    """A registered asset cannot be safely represented as a preview."""


def lookup_asset(conn, asset_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT asset_id, asset_name, layer, format, storage_uri, checksum "
            "FROM data_asset WHERE asset_id = %s",
            (asset_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(
        ("asset_id", "asset_name", "layer", "format", "storage_uri", "checksum"),
        row,
    ))


def read_gold_preview(asset, s3, gold_bucket, limit):
    """Only registered Gold URIs; verify bytes before presenting asset identity."""
    if asset["layer"] != "gold" or asset["format"] != "parquet":
        raise GoldPreviewError("Only Gold Parquet assets support this view.")
    uri = urlsplit(asset["storage_uri"])
    if (uri.scheme != "s3" or uri.netloc != gold_bucket or not uri.path.lstrip("/")
            or uri.query or uri.fragment):
        raise GoldPreviewError("Asset is outside the configured Gold storage.")
    obj = s3.get_object(Bucket=gold_bucket, Key=uri.path.lstrip("/"))
    body = obj["Body"]
    try:
        if obj.get("ContentLength", 0) > MAX_OBJECT_BYTES:
            raise GoldPreviewError("Gold file exceeds the 10 MiB preview limit.")
        data = body.read(MAX_OBJECT_BYTES + 1)
        if len(data) > MAX_OBJECT_BYTES:
            raise GoldPreviewError("Gold file exceeds the 10 MiB preview limit.")
    finally:
        body.close()
    if not asset.get("checksum") or hashlib.sha256(data).hexdigest() != asset["checksum"]:
        raise GoldPreviewError("Stored file differs from the registered checksum; select the latest asset.")
    parquet = pq.ParquetFile(io.BytesIO(data))
    if len(parquet.schema_arrow.names) > 50:
        raise GoldPreviewError("Gold preview supports at most 50 columns.")
    batch = next(parquet.iter_batches(batch_size=limit), None)
    # pandas converts nulls, timestamps and numeric scalars to valid JSON values.
    rows = json.loads(batch.to_pandas().to_json(orient="records", date_format="iso")) if batch else []
    result = {
        "asset_id": asset["asset_id"], "asset_name": asset["asset_name"],
        "storage_uri": asset["storage_uri"], "checksum_verified": True,
        "columns": parquet.schema_arrow.names,
        "total_rows": parquet.metadata.num_rows, "returned_rows": len(rows),
        "truncated": parquet.metadata.num_rows > len(rows), "rows": rows,
    }
    if len(json.dumps(result).encode()) > MAX_RESPONSE_BYTES:
        raise GoldPreviewError("Gold preview exceeds the 1 MiB response limit.")
    return result

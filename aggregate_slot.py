#!/usr/bin/env python3
"""
Aggregate 5-minute slot data from S3 (SeaweedFS) into the JSON format:

{
    "camera_id": "5deb576d1dc17d7c5515acfb",
    "slot": "2025-11-18 00:00:00",          # start of slot (đã bỏ T)
    "generated_at": "2025-11-18 00:05:00",  # = slot + 300s, cùng timezone/format
    "duration_sec": 300,
    "frames": [
        {
            "time": "2025-11-18T00:00:14",
            "image_ref": "/home/hung/LVTN/Camera/test_image/frames/..."
        },
        ...
    ],
    "speed": {
        "count": 5,
        "avg_kmh": 31.0,
        "min_kmh": 31.0,
        "max_kmh": 31.0,
        "series": [
            {
                "time": "2025-11-18 00:00:01",  # đã bỏ T
                "speed": 31.0
            },
            ...
        ]
    },
    "weather": { ... }
}
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import boto3

TZ_VN = timezone(timedelta(hours=7))
from botocore.exceptions import BotoCoreError, ClientError


# ========= S3 helpers =========


def create_s3_client(endpoint, access_key, secret_key, region):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


def list_json_keys(s3, bucket: str, prefix: str):
    """
    List tất cả object key .json trong bucket/prefix (handle phân trang).
    """
    keys = []
    if not prefix:
        return keys

    continuation_token = None

    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        try:
            resp = s3.list_objects_v2(**kwargs)
        except (BotoCoreError, ClientError) as e:
            sys.stderr.write(
                f"[WARN] list_objects_v2({bucket}, {prefix}) failed: {e}\n"
            )
            break

        contents = resp.get("Contents", [])
        for obj in contents:
            key = obj["Key"]
            if key.lower().endswith(".json"):
                keys.append(key)

        if not resp.get("IsTruncated"):
            break
        continuation_token = resp.get("NextContinuationToken")

    keys.sort()
    return keys


def load_json(s3, bucket: str, key: str):
    """
    Đọc object JSON từ S3 và parse thành Python object.
    """
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        data = resp["Body"].read().decode("utf-8")
        return json.loads(data)
    except (BotoCoreError, ClientError, ValueError) as e:
        sys.stderr.write(f"[WARN] Cannot load JSON s3://{bucket}/{key}: {e}\n")
        return None


# ========= Aggregation logic =========


def aggregate_slot(
    s3,
    camera_id: str,
    slot: str,  # ví dụ "2025-12-10T08:45:00"
    bucket: str,
    manifest_prefix: str,
    speed_prefix: str,
    weather_key: str | None,
):
    # ----- Parse slot & build slot_out, generated_at -----
    slot_dt = None
    # slot có thể là "YYYY-MM-DDTHH:MM:SS" hoặc "YYYY-MM-DD HH:MM:SS"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            slot_dt = datetime.strptime(slot, fmt)
            break
        except ValueError:
            continue

    if slot_dt is not None:
        slot_out = slot_dt.strftime("%Y-%m-%d %H:%M:%S")
        generated_at = (slot_dt + timedelta(seconds=300)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        # fallback: chỉ replace T, generated_at = now (UTC+7)
        slot_out = slot.replace("T", " ")
        generated_at = datetime.now(TZ_VN).strftime("%Y-%m-%d %H:%M:%S")

    # ----- 1) Frames từ manifest -----
    frames: list[dict] = []

    if manifest_prefix:
        manifest_keys = list_json_keys(s3, bucket, manifest_prefix)
        for key in manifest_keys:
            obj = load_json(s3, bucket, key)
            if not obj:
                continue

            # Hỗ trợ 2 style: mỗi file là object hoặc list object
            records = obj if isinstance(obj, list) else [obj]
            for m in records:
                t = m.get("time") or m.get("timestamp")
                # giữ nguyên time của frames (vẫn "YYYY-MM-DDTHH:MM:SS" nếu bạn muốn vậy)
                img_ref = m.get("image_ref") or m.get("image_key")
                if t and img_ref:
                    frames.append(
                        {
                            "time": t,
                            "image_ref": img_ref,
                        }
                    )

    # ----- 2) Speed series + thống kê -----
    speed_series: list[dict] = []

    if speed_prefix:
        speed_keys = list_json_keys(s3, bucket, speed_prefix)
        for key in speed_keys:
            obj = load_json(s3, bucket, key)
            if not obj:
                continue

            # Hỗ trợ object hoặc list
            records = obj if isinstance(obj, list) else [obj]
            for s in records:
                t = s.get("time") or s.get("timestamp")
                v = s.get("speed")
                if v is None:
                    continue
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
                if not t:
                    continue

                # Đổi time trong speed: "YYYY-MM-DDTHH:MM:SS" -> "YYYY-MM-DD HH:MM:SS"
                t_out = t.replace("T", " ")

                speed_series.append({"time": t_out, "speed": v})

    speed_obj = None
    if speed_series:
        vals = [p["speed"] for p in speed_series]
        avg = sum(vals) / len(vals)
        speed_obj = {
            "count": len(vals),
            "avg_kmh": avg,  # nếu muốn int: int(round(avg))
            "min_kmh": min(vals),
            "max_kmh": max(vals),
            "series": speed_series,
        }

    # ----- 3) Weather (1 file) -----
    weather = None
    if weather_key:
        weather = load_json(s3, bucket, weather_key)

    # ----- 4) Build aggregated JSON -----
    aggregated = {
        "camera_id": camera_id,
        "slot": slot_out,  # "YYYY-MM-DD HH:MM:SS"
        "generated_at": generated_at,  # slot + 300s, cùng format
        "duration_sec": 300,
        "frames": frames,
        "speed": speed_obj,
        "weather": weather,
    }

    return aggregated


# ========= CLI / main =========


def parse_args():
    parser = argparse.ArgumentParser(
        description="Aggregate 5-minute camera slot data from S3 (SeaweedFS)."
    )

    parser.add_argument("--camera-id", required=True, help="Camera ID")
    parser.add_argument(
        "--slot", required=True, help="Slot time, e.g. 2025-12-10T08:45:00"
    )
    parser.add_argument(
        "--bucket", required=True, help="S3 bucket name, e.g. traffic-data"
    )

    parser.add_argument(
        "--manifest-prefix", required=True, help="S3 prefix for manifest JSONs"
    )
    parser.add_argument(
        "--speed-prefix", required=True, help="S3 prefix for speed JSONs"
    )
    parser.add_argument(
        "--weather-key", required=False, default="", help="S3 key for weather JSON"
    )

    # S3 connection config (SeaweedFS)
    # IMPORTANT: Set environment variables S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY
    # Do NOT use hardcoded credentials in production
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("S3_ENDPOINT", "http://localhost:8333"),
        help="S3 endpoint URL (default: $S3_ENDPOINT or localhost:8333)",
    )
    parser.add_argument(
        "--access-key",
        default=os.environ.get("S3_ACCESS_KEY"),
        help="S3 access key (default: $S3_ACCESS_KEY) - REQUIRED",
    )
    parser.add_argument(
        "--secret-key",
        default=os.environ.get("S3_SECRET_KEY"),
        help="S3 secret key (default: $S3_SECRET_KEY) - REQUIRED",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("S3_REGION", "us-east-1"),
        help="S3 region (default: us-east-1 or $S3_REGION)",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if not args.access_key or not args.secret_key:
        sys.stderr.write(
            "[ERROR] S3_ACCESS_KEY and S3_SECRET_KEY environment variables are required.\n"
            "        Set them before running: export S3_ACCESS_KEY=... S3_SECRET_KEY=...\n"
        )
        sys.exit(1)

    s3 = create_s3_client(
        endpoint=args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
        region=args.region,
    )

    aggregated = aggregate_slot(
        s3=s3,
        camera_id=args.camera_id,
        slot=args.slot,
        bucket=args.bucket,
        manifest_prefix=args.manifest_prefix,
        speed_prefix=args.speed_prefix,
        weather_key=args.weather_key or None,
    )

    # In JSON ra stdout (ExecuteStreamCommand sẽ lấy làm content mới)
    json.dump(aggregated, sys.stdout, ensure_ascii=False)
    sys.stdout.flush()


if __name__ == "__main__":
    main()

CREATE SCHEMA IF NOT EXISTS iceberg.traffic
WITH (location = 's3://warehouse/traffic/');

CREATE TABLE IF NOT EXISTS iceberg.traffic.predicts (
    camera_id     VARCHAR NOT NULL,
    slot          TIMESTAMP(6) NOT NULL,
    count_preds   ARRAY(DOUBLE) NOT NULL,
    avg_kmh_preds ARRAY(DOUBLE) NOT NULL
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['day(slot)', 'camera_id']
);

-- Bảng đích của ingestion (DuckDB). Giữ nguyên giá trị nguồn; làm sạch thuộc tầng staging (dbt).

CREATE TABLE IF NOT EXISTS raw.yellow_tripdata (
    vendor_id               INTEGER,
    tpep_pickup_datetime    TIMESTAMP,
    tpep_dropoff_datetime   TIMESTAMP,
    passenger_count         BIGINT,
    trip_distance           DOUBLE,
    ratecode_id             BIGINT,
    store_and_fwd_flag      VARCHAR,
    pu_location_id          INTEGER,
    do_location_id          INTEGER,
    payment_type            BIGINT,
    fare_amount             DOUBLE,
    extra                   DOUBLE,
    mta_tax                 DOUBLE,
    tip_amount              DOUBLE,
    tolls_amount            DOUBLE,
    improvement_surcharge   DOUBLE,
    total_amount            DOUBLE,
    congestion_surcharge    DOUBLE,
    airport_fee             DOUBLE,
    cbd_congestion_fee      DOUBLE,      -- chỉ có từ 2025-01, NULL với 2024
    source_file_name        VARCHAR   NOT NULL,
    source_row_number       BIGINT,      -- số thứ tự dòng trong file Parquet, bắt đầu từ 1
    batch_id                BIGINT,      -- tăng dần theo mỗi lần nạp; Fact incremental dựa vào cột này
    load_datetime           TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS raw.taxi_zone_lookup (
    location_id       INTEGER,
    borough           VARCHAR,
    zone              VARCHAR,
    service_zone      VARCHAR,
    source_file_name  VARCHAR   NOT NULL,
    batch_id          BIGINT,
    load_datetime     TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE SEQUENCE IF NOT EXISTS control.etl_control_seq;

CREATE TABLE IF NOT EXISTS control.etl_control (
    control_id         BIGINT PRIMARY KEY DEFAULT nextval('control.etl_control_seq'),
    pipeline_name      VARCHAR,
    batch_id           BIGINT,
    source_file_name   VARCHAR,
    last_extract_time  TIMESTAMP,
    rows_read          BIGINT,
    rows_loaded        BIGINT,
    rows_rejected      BIGINT,
    status             VARCHAR,     -- SUCCESS / FAILED
    error_message      VARCHAR,
    started_at         TIMESTAMP,
    finished_at        TIMESTAMP
);

-- Phiên bản file nguồn đã nạp (theo HEAD của TLC). Mỗi lượt chạy so ETag/kích thước hiện tại với
-- bản đã ghi: khác nhau nghĩa là TLC đã phát hành lại file, cần tải và nạp lại (load_trips_to_raw.py).
CREATE TABLE IF NOT EXISTS control.source_file_meta (
    source_file_name   VARCHAR PRIMARY KEY,
    etag               VARCHAR,
    content_length     BIGINT,
    last_modified      VARCHAR,
    batch_id           BIGINT,      -- lần nạp ứng với phiên bản này (NULL nếu chỉ ghi mốc ban đầu)
    recorded_at        TIMESTAMP NOT NULL DEFAULT current_timestamp
);

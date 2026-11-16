CREATE TABLE IF NOT EXISTS stage.stg_yellow_taxi_trips (
    vendor_id               integer,
    tpep_pickup_datetime    timestamp,
    tpep_dropoff_datetime   timestamp,
    passenger_count         bigint,
    trip_distance           double precision,
    ratecode_id             bigint,
    store_and_fwd_flag      varchar(10),
    pu_location_id          integer,
    do_location_id          integer,
    payment_type            bigint,
    fare_amount             double precision,
    extra                   double precision,
    mta_tax                 double precision,
    tip_amount              double precision,
    tolls_amount            double precision,
    improvement_surcharge   double precision,
    total_amount            double precision,
    congestion_surcharge    double precision,
    airport_fee             double precision,
    cbd_congestion_fee      double precision,   -- chỉ có từ 2025-01, NULL với 2024
    source_file_name        varchar(200) NOT NULL,
    source_row_number       bigint,
    batch_id                bigint,
    load_datetime           timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stage.stg_taxi_zone_lookup (
    location_id       integer,
    borough           varchar(50),
    zone              varchar(120),
    service_zone      varchar(50),
    source_file_name  varchar(200) NOT NULL,
    batch_id          bigint,
    load_datetime     timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS control.etl_control (
    control_id         bigserial PRIMARY KEY,
    pipeline_name      varchar(100),
    batch_id           bigint,
    source_file_name   varchar(200),
    last_extract_time  timestamp,
    rows_read          bigint,
    rows_loaded        bigint,
    rows_rejected      bigint,
    status             varchar(20),   -- SUCCESS / FAILED
    error_message      text,
    started_at         timestamp,
    finished_at        timestamp
);
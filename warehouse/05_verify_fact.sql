-- ==============================================================================
-- NYC YELLOW TAXI DATA WAREHOUSE - KIỂM THỬ TẦNG FACT (DDS)
-- File: warehouse/05_verify_fact.sql
-- ==============================================================================

\echo '======================================================'
\echo '1. ĐỐI CHIẾU SỐ LƯỢNG DÒNG (STAGE VS FACT)'
\echo '======================================================'

WITH stage_count AS (
    SELECT count(*) AS total_stage FROM stage.stg_yellow_taxi_trips
),
fact_count AS (
    SELECT count(*) AS total_fact FROM dds.FactTaxiTrip
)
SELECT 
    s.total_stage,
    f.total_fact,
    (s.total_stage - f.total_fact) AS total_rejected,
    ROUND(((s.total_stage - f.total_fact)::numeric / s.total_stage) * 100, 2) AS rejected_pct
FROM stage_count s, fact_count f;


\echo '======================================================'
\echo '2. THỐNG KÊ CHI TIẾT CÁC LÝ DO LOẠI BẢN GHI RÁC'
\echo '======================================================'

SELECT
    count(*) FILTER (WHERE tpep_dropoff_datetime <= tpep_pickup_datetime) AS reason_invalid_duration,
    count(*) FILTER (WHERE tpep_pickup_datetime < '2024-01-01' OR tpep_pickup_datetime >= '2026-01-01') AS reason_out_of_period,
    count(*) FILTER (WHERE fare_amount < 0) AS reason_negative_fare,
    count(*) FILTER (WHERE total_amount < 0) AS reason_negative_total,
    count(*) FILTER (WHERE trip_distance < 0) AS reason_negative_distance
FROM stage.stg_yellow_taxi_trips;


\echo '======================================================'
\echo '3. KIỂM TRA TỶ LỆ KHÓA MỒ CÔI (GIÁ TRỊ UNKNOWN = -1)'
\echo '======================================================'

SELECT
    count(*) FILTER (WHERE PickupDateSK = -1)     AS unk_pickup_date,
    count(*) FILTER (WHERE DropoffDateSK = -1)    AS unk_dropoff_date,
    count(*) FILTER (WHERE PickupTimeSK = -1)     AS unk_pickup_time,
    count(*) FILTER (WHERE DropoffTimeSK = -1)    AS unk_dropoff_time,
    count(*) FILTER (WHERE PickupLocationSK = -1) AS unk_pu_loc,
    count(*) FILTER (WHERE DropoffLocationSK = -1)AS unk_do_loc,
    count(*) FILTER (WHERE VendorSK = -1)         AS unk_vendor,
    count(*) FILTER (WHERE PaymentTypeSK = -1)    AS unk_payment,
    count(*) FILTER (WHERE RateCodeSK = -1)       AS unk_ratecode,
    count(*) FILTER (WHERE PassengerGroupSK = -1) AS unk_passenger_group,
    count(*) FILTER (WHERE DistanceGroupSK = -1)  AS unk_distance_group
FROM dds.FactTaxiTrip;


\echo '======================================================'
\echo '4. KIỂM TRA PHÂN PHỐI DỮ LIỆU MEASURES (MIN - AVG - MAX)'
\echo '======================================================'

SELECT
    ROUND(MIN(TripDistance)::numeric, 2)            AS min_distance,
    ROUND(AVG(TripDistance)::numeric, 2)            AS avg_distance,
    ROUND(MAX(TripDistance)::numeric, 2)            AS max_distance,
    ROUND(MIN(TripDurationMinutes)::numeric, 2)     AS min_duration_mins,
    ROUND(AVG(TripDurationMinutes)::numeric, 2)     AS avg_duration_mins,
    ROUND(MAX(TripDurationMinutes)::numeric, 2)     AS max_duration_mins,
    ROUND(MIN(FareAmount)::numeric, 2)              AS min_fare,
    ROUND(AVG(FareAmount)::numeric, 2)              AS avg_fare,
    ROUND(MAX(FareAmount)::numeric, 2)              AS max_fare,
    ROUND(MIN(TotalAmount)::numeric, 2)             AS min_total,
    ROUND(AVG(TotalAmount)::numeric, 2)             AS avg_total,
    ROUND(MAX(TotalAmount)::numeric, 2)             AS max_total
FROM dds.FactTaxiTrip;


\echo '======================================================'
\echo '5. KIỂM TRA PHÂN PHỐI NẠP GIA TĂNG (THEO FILE & BATCH)'
\echo '======================================================'

SELECT 
    SourceFileName,
    BatchID,
    count(*) AS trip_count,
    MIN(LoadedAt) AS first_loaded_at,
    MAX(LoadedAt) AS last_loaded_at
FROM dds.FactTaxiTrip
GROUP BY SourceFileName, BatchID
ORDER BY BatchID;


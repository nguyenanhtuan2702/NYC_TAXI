-- ==============================================================================
-- NYC YELLOW TAXI DATA WAREHOUSE - TẦNG FACT (DDS)
-- File: warehouse/04_load_fact.sql
-- ==============================================================================

BEGIN;

-- Tối ưu tốc độ Bulk Load: Bỏ qua trigger kiểm tra FK từng dòng (do dữ liệu đã được LEFT JOIN + COALESCE(-1) chuẩn 100% với Dimension)
SET LOCAL session_replication_role = 'replica';

-- 1. Thực hiện trích xuất, biến đổi và nạp gia tăng vào Fact
INSERT INTO dds.FactTaxiTrip (
    PickupDateSK,
    DropoffDateSK,
    PickupTimeSK,
    DropoffTimeSK,
    PickupLocationSK,
    DropoffLocationSK,
    VendorSK,
    PaymentTypeSK,
    RateCodeSK,
    PassengerGroupSK,
    DistanceGroupSK,
    PickupDateTime,
    DropoffDateTime,
    TotalTrips,
    PassengerCount,
    TripDistance,
    TripDurationMinutes,
    FareAmount,
    Extra,
    MTATax,
    TipAmount,
    TollsAmount,
    ImprovementSurcharge,
    CongestionSurcharge,
    AirportFee,
    CBDCongestionFee,
    TotalAmount,
    -- Audit / Lineage Metadata
    SourceFileName,
    SourceRowNumber,
    BatchID,
    LoadedAt
)
SELECT
    -- 11 Khóa ngoại tra cứu từ Dimension với cơ chế xử lý lỗi COALESCE(..., -1)
    COALESCE(d_pu.DateSK, -1)                  AS PickupDateSK,
    COALESCE(d_do.DateSK, -1)                  AS DropoffDateSK,
    COALESCE(t_pu.TimeSK, -1)                  AS PickupTimeSK,
    COALESCE(t_do.TimeSK, -1)                  AS DropoffTimeSK,
    COALESCE(l_pu.LocationSK, -1)              AS PickupLocationSK,
    COALESCE(l_do.LocationSK, -1)              AS DropoffLocationSK,
    COALESCE(v.VendorSK, -1)                   AS VendorSK,
    COALESCE(p.PaymentTypeSK, -1)              AS PaymentTypeSK,
    COALESCE(r.RateCodeSK, -1)                 AS RateCodeSK,
    COALESCE(pg.PassengerGroupSK, -1)          AS PassengerGroupSK,
    COALESCE(dg.DistanceGroupSK, -1)           AS DistanceGroupSK,

    -- Thuộc tính thời gian chi tiết
    stg.tpep_pickup_datetime                   AS PickupDateTime,
    stg.tpep_dropoff_datetime                  AS DropoffDateTime,

    -- 14 Base Measures (Additive)
    1                                          AS TotalTrips,
    COALESCE(stg.passenger_count, 0)           AS PassengerCount,
    stg.trip_distance                          AS TripDistance,
    ROUND(EXTRACT(EPOCH FROM (stg.tpep_dropoff_datetime - stg.tpep_pickup_datetime)) / 60.0, 2) AS TripDurationMinutes,
    stg.fare_amount                            AS FareAmount,
    COALESCE(stg.extra, 0)                     AS Extra,
    COALESCE(stg.mta_tax, 0)                   AS MTATax,
    COALESCE(stg.tip_amount, 0)                AS TipAmount,
    COALESCE(stg.tolls_amount, 0)              AS TollsAmount,
    COALESCE(stg.improvement_surcharge, 0)     AS ImprovementSurcharge,
    COALESCE(stg.congestion_surcharge, 0)      AS CongestionSurcharge,
    COALESCE(stg.airport_fee, 0)               AS AirportFee,
    COALESCE(stg.cbd_congestion_fee, 0)        AS CBDCongestionFee,
    stg.total_amount                           AS TotalAmount,

    -- Thuộc tính kiểm toán & nguồn gốc
    stg.source_file_name                       AS SourceFileName,
    stg.source_row_number                      AS SourceRowNumber,
    stg.batch_id                               AS BatchID,
    CURRENT_TIMESTAMP                          AS LoadedAt

FROM stage.stg_yellow_taxi_trips stg

-- Tra cứu DimDate (Pickup & Dropoff)
LEFT JOIN dds.DimDate d_pu 
    ON d_pu.FullDate = stg.tpep_pickup_datetime::date
LEFT JOIN dds.DimDate d_do 
    ON d_do.FullDate = stg.tpep_dropoff_datetime::date

-- Tra cứu DimTime (Pickup & Dropoff)
LEFT JOIN dds.DimTime t_pu 
    ON t_pu.Hour = EXTRACT(HOUR FROM stg.tpep_pickup_datetime)::int 
   AND t_pu.Minute = EXTRACT(MINUTE FROM stg.tpep_pickup_datetime)::int
LEFT JOIN dds.DimTime t_do 
    ON t_do.Hour = EXTRACT(HOUR FROM stg.tpep_dropoff_datetime)::int 
   AND t_do.Minute = EXTRACT(MINUTE FROM stg.tpep_dropoff_datetime)::int

-- Tra cứu DimLocation (Pickup & Dropoff)
LEFT JOIN dds.DimLocation l_pu 
    ON l_pu.LocationID = stg.pu_location_id
LEFT JOIN dds.DimLocation l_do 
    ON l_do.LocationID = stg.do_location_id

-- Tra cứu DimVendor
LEFT JOIN dds.DimVendor v 
    ON v.VendorID = stg.vendor_id

-- Tra cứu DimPaymentType
LEFT JOIN dds.DimPaymentType p 
    ON p.PaymentTypeID = stg.payment_type

-- Tra cứu DimRateCode (Gán NULL -> 99 để khớp danh mục)
LEFT JOIN dds.DimRateCode r 
    ON r.RateCodeID = COALESCE(stg.ratecode_id, 99)

-- Tra cứu DimPassengerGroup (Theo khoảng MinPassengers - MaxPassengers)
LEFT JOIN dds.DimPassengerGroup pg 
    ON stg.passenger_count BETWEEN pg.MinPassengers AND pg.MaxPassengers

-- Tra cứu DimDistanceGroup (Theo khoảng MinDistance - MaxDistance)
LEFT JOIN dds.DimDistanceGroup dg 
    ON stg.trip_distance BETWEEN dg.MinDistance AND dg.MaxDistance

-- BỘ LỌC CHẤT LƯỢNG DỮ LIỆU (Data Quality Rules)
WHERE stg.tpep_dropoff_datetime > stg.tpep_pickup_datetime
  AND stg.tpep_pickup_datetime >= '2024-01-01'
  AND stg.tpep_pickup_datetime < '2026-01-01'
  AND stg.fare_amount >= 0
  AND stg.total_amount >= 0
  AND stg.trip_distance >= 0

  -- ĐIỀU KIỆN NẠP GIA TĂNG (INCREMENTAL WATERMARK)
  -- Chỉ nạp các lô dữ liệu (Batch) mới chưa từng có trong Fact.
  -- Lần đầu (Fact rỗng): COALESCE trả về 0, toàn bộ dữ liệu hợp lệ trong stage sẽ được nạp.
  -- Các lần sau: Chỉ nạp dữ liệu từ các BatchID lớn hơn BatchID lớn nhất hiện có.
  AND stg.batch_id > (SELECT COALESCE(MAX(BatchID), 0) FROM dds.FactTaxiTrip);

COMMIT;

-- ==========================================
-- 1. Load DimLocation
-- Từ bảng tham chiếu stage.stg_taxi_zone_lookup
-- ==========================================
-- ==========================================
-- 1. Load DimLocation
-- Từ bảng tham chiếu stage.stg_taxi_zone_lookup
-- ==========================================
INSERT INTO dds.DimLocation (LocationID, Borough, Zone, ServiceZone)
SELECT DISTINCT 
    location_id, 
    borough, 
    zone, 
    service_zone
FROM stage.stg_taxi_zone_lookup
WHERE location_id IS NOT NULL;


-- ==========================================
-- 2. Load DimVendor
-- Xử lý mã lạ (6, 7) thành Unknown
-- ==========================================
INSERT INTO dds.DimVendor (VendorID, VendorName)
SELECT DISTINCT 
    vendor_id,
    CASE 
        WHEN vendor_id = 1 THEN 'Creative Mobile Technologies'
        WHEN vendor_id = 2 THEN 'VeriFone Inc.'
        ELSE 'Unknown' 
    END AS VendorName
FROM stage.stg_yellow_taxi_trips
WHERE vendor_id IS NOT NULL;


-- ==========================================
-- 3. Load DimPaymentType
-- Xử lý mã 0 (Flex Fare) thành Unknown
-- ==========================================
INSERT INTO dds.DimPaymentType (PaymentTypeID, PaymentTypeName)
SELECT DISTINCT 
    payment_type,
    CASE 
        WHEN payment_type = 1 THEN 'Credit card'
        WHEN payment_type = 2 THEN 'Cash'
        WHEN payment_type = 3 THEN 'No charge'
        WHEN payment_type = 4 THEN 'Dispute'
        WHEN payment_type = 5 THEN 'Unknown'
        WHEN payment_type = 6 THEN 'Voided trip'
        ELSE 'Unknown' 
    END AS PaymentTypeName
FROM stage.stg_yellow_taxi_trips
WHERE payment_type IS NOT NULL;


-- ==========================================
-- 4. Load DimRateCode
-- Xử lý mã 99 và NULL thành Unknown (ID 99)
-- ==========================================
INSERT INTO dds.DimRateCode (RateCodeID, RateCodeName)
SELECT DISTINCT 
    COALESCE(ratecode_id, 99) AS RateCodeID,
    CASE 
        WHEN ratecode_id = 1 THEN 'Standard rate'
        WHEN ratecode_id = 2 THEN 'JFK'
        WHEN ratecode_id = 3 THEN 'Newark'
        WHEN ratecode_id = 4 THEN 'Nassau or Westchester'
        WHEN ratecode_id = 5 THEN 'Negotiated fare'
        WHEN ratecode_id = 6 THEN 'Group ride'
        ELSE 'Unknown' 
    END AS RateCodeName
FROM stage.stg_yellow_taxi_trips;


-- ==========================================
-- 5. Load DimPassengerGroup
-- Phân loại nhóm hành khách tĩnh
-- ==========================================
INSERT INTO dds.DimPassengerGroup (PassengerGroupCode, PassengerGroupName, MinPassengers, MaxPassengers)
VALUES 
    ('SINGLE', '1 hành khách', 1, 1),
    ('SMALL', 'Nhóm 2-4 người', 2, 4),
    ('LARGE', 'Nhóm từ 5 người trở lên', 5, 99);


-- ==========================================
-- 6. Load DimDistanceGroup
-- Phân loại độ dài chuyến đi tĩnh
-- ==========================================
INSERT INTO dds.DimDistanceGroup (DistanceGroupCode, DistanceGroupName, MinDistance, MaxDistance)
VALUES 
    ('SHORT', 'Dưới 2 miles', 0.00, 1.99),
    ('MEDIUM', '2 đến 5 miles', 2.00, 5.00),
    ('LONG', 'Trên 5 miles', 5.01, 9999.99);


-- ==========================================
-- 7. Load DimDate
-- Generate dữ liệu ngày cho 2 năm 2024-2025
-- ==========================================
INSERT INTO dds.DimDate (FullDate, Day, DayOfWeek, DayName, WeekOfYear, Month, MonthName, Quarter, Year)
SELECT 
    datum AS FullDate,
    EXTRACT(DAY FROM datum) AS Day,
    EXTRACT(ISODOW FROM datum) AS DayOfWeek,
    TRIM(TO_CHAR(datum, 'Day')) AS DayName,
    EXTRACT(WEEK FROM datum) AS WeekOfYear,
    EXTRACT(MONTH FROM datum) AS Month,
    TRIM(TO_CHAR(datum, 'Month')) AS MonthName,
    EXTRACT(QUARTER FROM datum) AS Quarter,
    EXTRACT(YEAR FROM datum) AS Year
FROM (
    SELECT '2024-01-01'::DATE + sequence.day AS datum
    FROM generate_series(0, 730) AS sequence(day)
) dq
WHERE EXTRACT(YEAR FROM datum) IN (2024, 2025);


-- ==========================================
-- 8. Load DimTime
-- Generate dữ liệu 24h
-- ==========================================
INSERT INTO dds.DimTime (Hour, Minute, TimeOfDay, TimeSlot)
SELECT 
    h AS Hour,
    m AS Minute,
    CASE
        WHEN h >= 5 AND h < 12 THEN 'Morning'
        WHEN h >= 12 AND h < 17 THEN 'Afternoon'
        WHEN h >= 17 AND h < 21 THEN 'Evening'
        ELSE 'Night'
    END AS TimeOfDay,
    CONCAT(LPAD(h::TEXT, 2, '0'), ':00 - ', LPAD((h+1)::TEXT, 2, '0'), ':00') AS TimeSlot
FROM generate_series(0, 23) h, generate_series(0, 59) m;
-- Khởi tạo schema dds 
CREATE SCHEMA IF NOT EXISTS dds;

-- ==========================================
-- 1. DimDate
-- ==========================================
DROP TABLE IF EXISTS dds.DimDate CASCADE;
CREATE TABLE dds.DimDate (
    DateSK SERIAL PRIMARY KEY,
    FullDate DATE,
    Day INT,
    DayOfWeek INT,
    DayName VARCHAR(20),
    WeekOfYear INT,
    Month INT,
    MonthName VARCHAR(20),
    Quarter INT,
    Year INT
);

-- Khởi tạo dòng Unknown
INSERT INTO dds.DimDate (DateSK, FullDate, Day, DayOfWeek, DayName, WeekOfYear, Month, MonthName, Quarter, Year)
VALUES (-1, '1900-01-01', -1, -1, 'Unknown', -1, -1, 'Unknown', -1, -1);


-- ==========================================
-- 2. DimTime
-- ==========================================
DROP TABLE IF EXISTS dds.DimTime CASCADE;
CREATE TABLE dds.DimTime (
    TimeSK SERIAL PRIMARY KEY,
    Hour INT,
    Minute INT,
    TimeOfDay VARCHAR(20),
    TimeSlot VARCHAR(50)
);

-- Khởi tạo dòng Unknown
INSERT INTO dds.DimTime (TimeSK, Hour, Minute, TimeOfDay, TimeSlot)
VALUES (-1, -1, -1, 'Unknown', 'Unknown');


-- ==========================================
-- 3. DimLocation
-- ==========================================
DROP TABLE IF EXISTS dds.DimLocation CASCADE;
CREATE TABLE dds.DimLocation (
    LocationSK SERIAL PRIMARY KEY,
    LocationID INT,
    Borough VARCHAR(50),
    Zone VARCHAR(100),
    ServiceZone VARCHAR(50)
);

-- Khởi tạo dòng Unknown
INSERT INTO dds.DimLocation (LocationSK, LocationID, Borough, Zone, ServiceZone)
VALUES (-1, -1, 'Unknown', 'Unknown', 'Unknown');


-- ==========================================
-- 4. DimVendor
-- ==========================================
DROP TABLE IF EXISTS dds.DimVendor CASCADE;
CREATE TABLE dds.DimVendor (
    VendorSK SERIAL PRIMARY KEY,
    VendorID INT,
    VendorName VARCHAR(50)
);

-- Khởi tạo dòng Unknown
INSERT INTO dds.DimVendor (VendorSK, VendorID, VendorName)
VALUES (-1, -1, 'Unknown');


-- ==========================================
-- 5. DimPaymentType
-- ==========================================
DROP TABLE IF EXISTS dds.DimPaymentType CASCADE;
CREATE TABLE dds.DimPaymentType (
    PaymentTypeSK SERIAL PRIMARY KEY,
    PaymentTypeID INT,
    PaymentTypeName VARCHAR(50)
);

-- Khởi tạo dòng Unknown
INSERT INTO dds.DimPaymentType (PaymentTypeSK, PaymentTypeID, PaymentTypeName)
VALUES (-1, -1, 'Unknown');


-- ==========================================
-- 6. DimRateCode
-- ==========================================
DROP TABLE IF EXISTS dds.DimRateCode CASCADE;
CREATE TABLE dds.DimRateCode (
    RateCodeSK SERIAL PRIMARY KEY,
    RateCodeID INT,
    RateCodeName VARCHAR(50)
);

-- Khởi tạo dòng Unknown
INSERT INTO dds.DimRateCode (RateCodeSK, RateCodeID, RateCodeName)
VALUES (-1, -1, 'Unknown');


-- ==========================================
-- 7. DimPassengerGroup
-- ==========================================
DROP TABLE IF EXISTS dds.DimPassengerGroup CASCADE;
CREATE TABLE dds.DimPassengerGroup (
    PassengerGroupSK SERIAL PRIMARY KEY,
    PassengerGroupCode VARCHAR(20),
    PassengerGroupName VARCHAR(50),
    MinPassengers INT,
    MaxPassengers INT
);

-- Khởi tạo dòng Unknown
INSERT INTO dds.DimPassengerGroup (PassengerGroupSK, PassengerGroupCode, PassengerGroupName, MinPassengers, MaxPassengers)
VALUES (-1, 'UNK', 'Unknown', -1, -1);


-- ==========================================
-- 8. DimDistanceGroup
-- ==========================================
DROP TABLE IF EXISTS dds.DimDistanceGroup CASCADE;
CREATE TABLE dds.DimDistanceGroup (
    DistanceGroupSK SERIAL PRIMARY KEY,
    DistanceGroupCode VARCHAR(20),
    DistanceGroupName VARCHAR(50),
    MinDistance NUMERIC(10,2),
    MaxDistance NUMERIC(10,2)
);

-- Khởi tạo dòng Unknown
INSERT INTO dds.DimDistanceGroup (DistanceGroupSK, DistanceGroupCode, DistanceGroupName, MinDistance, MaxDistance)
VALUES (-1, 'UNK', 'Unknown', -1, -1);
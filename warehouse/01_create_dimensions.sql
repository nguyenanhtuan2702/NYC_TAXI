-- Khởi tạo schema dds 
CREATE SCHEMA IF NOT EXISTS dds;

-- ==========================================
-- 1. DimDate
-- ==========================================
CREATE TABLE IF NOT EXISTS dds.DimDate (
    DateSK SERIAL PRIMARY KEY,
    FullDate DATE UNIQUE NOT NULL,
    Day INT,
    DayOfWeek INT,
    DayName VARCHAR(20),
    WeekOfYear INT,
    Month INT,
    MonthName VARCHAR(20),
    Quarter INT,
    Year INT
);

INSERT INTO dds.DimDate (DateSK, FullDate, Day, DayOfWeek, DayName, WeekOfYear, Month, MonthName, Quarter, Year)
VALUES (-1, '1900-01-01', -1, -1, 'Unknown', -1, -1, 'Unknown', -1, -1)
ON CONFLICT (FullDate) DO NOTHING;

-- ==========================================
-- 2. DimTime
-- ==========================================
CREATE TABLE IF NOT EXISTS dds.DimTime (
    TimeSK SERIAL PRIMARY KEY,
    Hour INT,
    Minute INT,
    TimeOfDay VARCHAR(20),
    TimeSlot VARCHAR(50),
    UNIQUE (Hour, Minute)
);

INSERT INTO dds.DimTime (TimeSK, Hour, Minute, TimeOfDay, TimeSlot)
VALUES (-1, -1, -1, 'Unknown', 'Unknown')
ON CONFLICT (Hour, Minute) DO NOTHING;

-- ==========================================
-- 3. DimLocation
-- ==========================================
CREATE TABLE IF NOT EXISTS dds.DimLocation (
    LocationSK SERIAL PRIMARY KEY,
    LocationID INT UNIQUE NOT NULL,
    Borough VARCHAR(50),
    Zone VARCHAR(100),
    ServiceZone VARCHAR(50)
);

INSERT INTO dds.DimLocation (LocationSK, LocationID, Borough, Zone, ServiceZone)
VALUES (-1, -1, 'Unknown', 'Unknown', 'Unknown')
ON CONFLICT (LocationID) DO NOTHING;

-- ==========================================
-- 4. DimVendor
-- ==========================================
CREATE TABLE IF NOT EXISTS dds.DimVendor (
    VendorSK SERIAL PRIMARY KEY,
    VendorID INT UNIQUE NOT NULL,
    VendorName VARCHAR(50)
);

INSERT INTO dds.DimVendor (VendorSK, VendorID, VendorName)
VALUES (-1, -1, 'Unknown')
ON CONFLICT (VendorID) DO NOTHING;

-- ==========================================
-- 5. DimPaymentType
-- ==========================================
CREATE TABLE IF NOT EXISTS dds.DimPaymentType (
    PaymentTypeSK SERIAL PRIMARY KEY,
    PaymentTypeID INT UNIQUE NOT NULL,
    PaymentTypeName VARCHAR(50)
);

INSERT INTO dds.DimPaymentType (PaymentTypeSK, PaymentTypeID, PaymentTypeName)
VALUES (-1, -1, 'Unknown')
ON CONFLICT (PaymentTypeID) DO NOTHING;

-- ==========================================
-- 6. DimRateCode
-- ==========================================
CREATE TABLE IF NOT EXISTS dds.DimRateCode (
    RateCodeSK SERIAL PRIMARY KEY,
    RateCodeID INT UNIQUE NOT NULL,
    RateCodeName VARCHAR(50)
);

INSERT INTO dds.DimRateCode (RateCodeSK, RateCodeID, RateCodeName)
VALUES (-1, -1, 'Unknown')
ON CONFLICT (RateCodeID) DO NOTHING;

-- ==========================================
-- 7. DimPassengerGroup
-- ==========================================
CREATE TABLE IF NOT EXISTS dds.DimPassengerGroup (
    PassengerGroupSK SERIAL PRIMARY KEY,
    PassengerGroupCode VARCHAR(20) UNIQUE NOT NULL,
    PassengerGroupName VARCHAR(50),
    MinPassengers INT,
    MaxPassengers INT
);

INSERT INTO dds.DimPassengerGroup (PassengerGroupSK, PassengerGroupCode, PassengerGroupName, MinPassengers, MaxPassengers)
VALUES (-1, 'UNK', 'Unknown', -1, -1)
ON CONFLICT (PassengerGroupCode) DO NOTHING;

-- ==========================================
-- 8. DimDistanceGroup
-- ==========================================
CREATE TABLE IF NOT EXISTS dds.DimDistanceGroup (
    DistanceGroupSK SERIAL PRIMARY KEY,
    DistanceGroupCode VARCHAR(20) UNIQUE NOT NULL,
    DistanceGroupName VARCHAR(50),
    MinDistance NUMERIC(10,4),
    MaxDistance NUMERIC(10,4)
);

INSERT INTO dds.DimDistanceGroup (DistanceGroupSK, DistanceGroupCode, DistanceGroupName, MinDistance, MaxDistance)
VALUES (-1, 'UNK', 'Unknown', -1, -1)
ON CONFLICT (DistanceGroupCode) DO NOTHING;
-- ==============================================================================
-- NYC YELLOW TAXI DATA WAREHOUSE - TẦNG FACT (DDS)
-- File: warehouse/03_create_fact.sql
-- ==============================================================================

CREATE SCHEMA IF NOT EXISTS dds;

-- 1. Tạo bảng FactTaxiTrip chuẩn theo Star Schema (Idempotent DDL - Không xóa dữ liệu cũ)
CREATE TABLE IF NOT EXISTS dds.FactTaxiTrip (
    -- Khóa chính Surrogate Key
    TripSK                  BIGSERIAL PRIMARY KEY,

    -- 11 Khóa ngoại liên kết 8 Dimension (Foreign Keys)
    PickupDateSK            INT NOT NULL REFERENCES dds.DimDate(DateSK),
    DropoffDateSK           INT NOT NULL REFERENCES dds.DimDate(DateSK),
    PickupTimeSK            INT NOT NULL REFERENCES dds.DimTime(TimeSK),
    DropoffTimeSK           INT NOT NULL REFERENCES dds.DimTime(TimeSK),
    PickupLocationSK        INT NOT NULL REFERENCES dds.DimLocation(LocationSK),
    DropoffLocationSK       INT NOT NULL REFERENCES dds.DimLocation(LocationSK),
    VendorSK                INT NOT NULL REFERENCES dds.DimVendor(VendorSK),
    PaymentTypeSK           INT NOT NULL REFERENCES dds.DimPaymentType(PaymentTypeSK),
    RateCodeSK              INT NOT NULL REFERENCES dds.DimRateCode(RateCodeSK),
    PassengerGroupSK        INT NOT NULL REFERENCES dds.DimPassengerGroup(PassengerGroupSK),
    DistanceGroupSK         INT NOT NULL REFERENCES dds.DimDistanceGroup(DistanceGroupSK),

    -- Thuộc tính thời gian (Degenerate Dimensions)
    PickupDateTime          TIMESTAMP NOT NULL,
    DropoffDateTime         TIMESTAMP NOT NULL,

    -- 14 Base Measures (Tất cả đều là Additive)
    TotalTrips              INT NOT NULL DEFAULT 1,
    PassengerCount          INT,
    TripDistance            DOUBLE PRECISION,
    TripDurationMinutes     DOUBLE PRECISION,
    FareAmount              DOUBLE PRECISION,
    Extra                   DOUBLE PRECISION,
    MTATax                  DOUBLE PRECISION,
    TipAmount               DOUBLE PRECISION,
    TollsAmount             DOUBLE PRECISION,
    ImprovementSurcharge    DOUBLE PRECISION,
    CongestionSurcharge     DOUBLE PRECISION,
    AirportFee              DOUBLE PRECISION,
    CBDCongestionFee        DOUBLE PRECISION,
    TotalAmount             DOUBLE PRECISION,

    -- Thuộc tính kiểm toán & nguồn gốc dữ liệu (Audit / Lineage - Phục vụ nạp gia tăng Incremental)
    SourceFileName          VARCHAR(200),
    SourceRowNumber         BIGINT,
    BatchID                 BIGINT,
    LoadedAt                TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tạo các chỉ mục (Indexes) trên các khóa ngoại hay dùng để tối ưu truy vấn OLAP & Nạp gia tăng
CREATE INDEX IF NOT EXISTS idx_fact_pickup_date ON dds.FactTaxiTrip(PickupDateSK);
CREATE INDEX IF NOT EXISTS idx_fact_dropoff_date ON dds.FactTaxiTrip(DropoffDateSK);
CREATE INDEX IF NOT EXISTS idx_fact_pickup_time ON dds.FactTaxiTrip(PickupTimeSK);
CREATE INDEX IF NOT EXISTS idx_fact_pickup_loc ON dds.FactTaxiTrip(PickupLocationSK);
CREATE INDEX IF NOT EXISTS idx_fact_dropoff_loc ON dds.FactTaxiTrip(DropoffLocationSK);
CREATE INDEX IF NOT EXISTS idx_fact_vendor ON dds.FactTaxiTrip(VendorSK);
CREATE INDEX IF NOT EXISTS idx_fact_payment ON dds.FactTaxiTrip(PaymentTypeSK);
CREATE INDEX IF NOT EXISTS idx_fact_ratecode ON dds.FactTaxiTrip(RateCodeSK);
CREATE INDEX IF NOT EXISTS idx_fact_distance_group ON dds.FactTaxiTrip(DistanceGroupSK);
CREATE INDEX IF NOT EXISTS idx_fact_passenger_group ON dds.FactTaxiTrip(PassengerGroupSK);
CREATE INDEX IF NOT EXISTS idx_fact_batch_id ON dds.FactTaxiTrip(BatchID);
CREATE INDEX IF NOT EXISTS idx_fact_source_file ON dds.FactTaxiTrip(SourceFileName);
CREATE INDEX IF NOT EXISTS idx_fact_loaded_at ON dds.FactTaxiTrip(LoadedAt);

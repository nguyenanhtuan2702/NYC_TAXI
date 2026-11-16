-- ĐẾM SỐ DÒNG NULL Ở TỪNG CỘT + KHOẢNG THỜI GIAN CỦA DỮ LIỆU (bảng staging)
SELECT
  -- Tổng số dòng trong bảng
  count(*) AS tong_dong,

  -- ---------- SỐ DÒNG NULL: VENDOR VÀ THỜI GIAN ----------
  count(*)-count(vendor_id) AS vendor_id,                       -- NULL ở vendor_id
  count(*)-count(tpep_pickup_datetime) AS pickup,               -- NULL ở giờ đón
  count(*)-count(tpep_dropoff_datetime) AS dropoff,             -- NULL ở giờ trả

  -- ---------- SỐ DÒNG NULL: CHUYẾN ĐI ----------
  count(*)-count(passenger_count) AS passenger_count,           -- NULL ở số hành khách
  count(*)-count(trip_distance) AS trip_distance,               -- NULL ở quãng đường
  count(*)-count(ratecode_id) AS ratecode_id,                   -- NULL ở loại biểu phí
  count(*)-count(store_and_fwd_flag) AS store_fwd,              -- NULL ở store_and_fwd_flag

  -- ---------- SỐ DÒNG NULL: ĐỊA ĐIỂM VÀ THANH TOÁN ----------
  count(*)-count(pu_location_id) AS pu_loc,                     -- NULL ở khu vực đón
  count(*)-count(do_location_id) AS do_loc,                     -- NULL ở khu vực trả
  count(*)-count(payment_type) AS payment_type,                 -- NULL ở hình thức thanh toán

  -- ---------- SỐ DÒNG NULL: CÁC KHOẢN TIỀN ----------
  count(*)-count(fare_amount) AS fare,                          -- NULL ở tiền cước
  count(*)-count(extra) AS extra,                               -- NULL ở phụ phí extra
  count(*)-count(mta_tax) AS mta_tax,                           -- NULL ở thuế MTA
  count(*)-count(tip_amount) AS tip,                            -- NULL ở tiền boa
  count(*)-count(tolls_amount) AS tolls,                        -- NULL ở phí cầu đường
  count(*)-count(improvement_surcharge) AS improvement,         -- NULL ở phí cải thiện dịch vụ
  count(*)-count(total_amount) AS total,                        -- NULL ở tổng tiền
  count(*)-count(congestion_surcharge) AS congestion,           -- NULL ở phụ phí ùn tắc
  count(*)-count(airport_fee) AS airport_fee,                   -- NULL ở phí sân bay
  count(*)-count(cbd_congestion_fee) AS cbd_fee,                -- NULL ở phí ùn tắc khu trung tâm

  -- ---------- KHOẢNG THỜI GIAN CỦA DỮ LIỆU ----------
  min(tpep_pickup_datetime) AS pickup_min,                      -- giờ đón sớm nhất
  max(tpep_pickup_datetime) AS pickup_max,                      -- giờ đón muộn nhất
  min(tpep_dropoff_datetime) AS dropoff_min,                    -- giờ trả sớm nhất
  max(tpep_dropoff_datetime) AS dropoff_max                     -- giờ trả muộn nhất
FROM stage.stg_yellow_taxi_trips;   -- bảng staging
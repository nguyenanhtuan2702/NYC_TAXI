-- KIỂM TRA CHẤT LƯỢNG DỮ LIỆU TRÊN BẢNG STAGING
-- Mỗi cột kết quả = số dòng thỏa một điều kiện (đếm bằng COUNT + FILTER).
SELECT
  -- Tổng số dòng trong bảng
  count(*)                                                        AS tong_dong,

  -- ---------- VENDOR ----------
  -- Đếm dòng có vendor_id bị NULL
  count(*) FILTER (WHERE vendor_id IS NULL)                       AS vendor_null,
  -- Đếm dòng có vendor_id khác 1 và 2 (dòng NULL không được đếm ở đây)
  count(*) FILTER (WHERE vendor_id NOT IN (1,2))                  AS vendor_la,

  -- ---------- THỜI GIAN ----------
  -- Đếm dòng thiếu giờ đón
  count(*) FILTER (WHERE tpep_pickup_datetime IS NULL)            AS pickup_null,
  -- Đếm dòng thiếu giờ trả
  count(*) FILTER (WHERE tpep_dropoff_datetime IS NULL)           AS dropoff_null,
  -- Đếm dòng có giờ đón trước 01/01/2024 hoặc từ 01/01/2026 trở đi
  count(*) FILTER (WHERE tpep_pickup_datetime < '2024-01-01'
                      OR tpep_pickup_datetime >= '2026-01-01')    AS pickup_ngoai_ky,
  -- Đếm dòng có giờ trả sớm hơn giờ đón
  count(*) FILTER (WHERE tpep_dropoff_datetime < tpep_pickup_datetime) AS dropoff_truoc_pickup,

  -- ---------- HÀNH KHÁCH ----------
  -- Đếm dòng thiếu số hành khách
  count(*) FILTER (WHERE passenger_count IS NULL)                 AS pax_null,
  -- Đếm dòng có số hành khách bằng 0
  count(*) FILTER (WHERE passenger_count = 0)                     AS pax_0,

  -- ---------- QUÃNG ĐƯỜNG ----------
  -- Đếm dòng có quãng đường nhỏ hơn hoặc bằng 0
  count(*) FILTER (WHERE trip_distance <= 0)                      AS dist_le_0,

  -- ---------- TIỀN ----------
  -- Đếm dòng có tiền cước âm
  count(*) FILTER (WHERE fare_amount < 0)                         AS fare_am,
  -- Đếm dòng có tổng tiền âm
  count(*) FILTER (WHERE total_amount < 0)                        AS total_am,

  -- ---------- ĐỊA ĐIỂM ----------
  -- Đếm dòng có mã khu vực đón hoặc trả nằm ngoài khoảng 1-265
  count(*) FILTER (WHERE pu_location_id NOT BETWEEN 1 AND 265
                      OR do_location_id NOT BETWEEN 1 AND 265)    AS location_ngoai_1_265,
  -- Đếm dòng có mã khu vực đón hoặc trả là 264 hoặc 265
  count(*) FILTER (WHERE pu_location_id IN (264,265)
                      OR do_location_id IN (264,265))             AS location_unknown,

  -- ---------- LOẠI BIỂU PHÍ ----------
  -- Đếm dòng có ratecode_id = 99
  count(*) FILTER (WHERE ratecode_id = 99)                        AS ratecode_99,
  -- Đếm dòng thiếu ratecode_id
  count(*) FILTER (WHERE ratecode_id IS NULL)                     AS ratecode_null,

  -- ---------- HÌNH THỨC THANH TOÁN ----------
  -- Đếm dòng có payment_type = 0
  count(*) FILTER (WHERE payment_type = 0)                        AS payment_0,
  -- Đếm dòng thiếu payment_type
  count(*) FILTER (WHERE payment_type IS NULL)                    AS payment_null

FROM stage.stg_yellow_taxi_trips;   -- bảng staging
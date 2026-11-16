-- KIỂM TRA GIÁ TRỊ BẤT THƯỜNG TRÊN BẢNG STAGING
-- Gồm 3 phần: (1) giá trị nhỏ nhất/lớn nhất, (2) đếm dòng vượt ngưỡng,
-- (3) đếm dòng có khoản tiền bị âm.
-- Mỗi cột kết quả là một con số (min, max hoặc số dòng).

SELECT
  -- ---------- PHẦN 1: GIÁ TRỊ NHỎ NHẤT / LỚN NHẤT ----------
  min(trip_distance) AS dist_min, max(trip_distance) AS dist_max,     -- quãng đường
  min(fare_amount) AS fare_min, max(fare_amount) AS fare_max,         -- tiền cước
  min(total_amount) AS total_min, max(total_amount) AS total_max,     -- tổng tiền
  max(passenger_count) AS pax_max,                                    -- số hành khách lớn nhất

  -- ---------- PHẦN 2: ĐẾM DÒNG VƯỢT NGƯỠNG ----------
  -- Đếm dòng có quãng đường lớn hơn 100
  count(*) FILTER (WHERE trip_distance > 100) AS dist_gt_100,
  -- Đếm dòng có tiền cước lớn hơn 500
  count(*) FILTER (WHERE fare_amount > 500) AS fare_gt_500,
  -- Đếm dòng có tổng tiền lớn hơn 1000
  count(*) FILTER (WHERE total_amount > 1000) AS total_gt_1000,
  -- Đếm dòng có số hành khách lớn hơn 6
  count(*) FILTER (WHERE passenger_count > 6) AS pax_gt_6,
  -- Đếm dòng có giờ trả bằng giờ đón (thời lượng = 0)
  count(*) FILTER (WHERE tpep_dropoff_datetime = tpep_pickup_datetime) AS duration_0,
  -- Đếm dòng có thời lượng chuyến đi dài hơn 24 giờ
  count(*) FILTER (WHERE tpep_dropoff_datetime - tpep_pickup_datetime > interval '24 hours') AS duration_gt_24h,

  -- Đếm dòng có vận tốc lớn hơn 100 mph. Điều kiện gồm:
  --   giờ trả sau giờ đón, quãng đường > 0,
  --   vận tốc = quãng đường / số giờ (số giây đổi ra giờ bằng cách chia 3600)
  --   NULLIF(..., 0) đổi thời lượng 0 thành NULL để tránh lỗi chia cho 0
  count(*) FILTER (WHERE tpep_dropoff_datetime > tpep_pickup_datetime AND trip_distance > 0
    AND trip_distance / (NULLIF(extract(epoch FROM tpep_dropoff_datetime - tpep_pickup_datetime),0)/3600.0) > 100) AS speed_gt_100mph,

  -- ---------- PHẦN 3: ĐẾM DÒNG CÓ KHOẢN TIỀN ÂM ----------
  count(*) FILTER (WHERE extra < 0) AS extra_am,                      -- phụ phí extra âm
  count(*) FILTER (WHERE mta_tax < 0) AS mta_tax_am,                  -- thuế MTA âm
  count(*) FILTER (WHERE tip_amount < 0) AS tip_am,                   -- tiền boa âm
  count(*) FILTER (WHERE tolls_amount < 0) AS tolls_am,               -- phí cầu đường âm
  count(*) FILTER (WHERE improvement_surcharge < 0) AS improvement_am, -- phí cải thiện dịch vụ âm
  count(*) FILTER (WHERE congestion_surcharge < 0) AS congestion_am,  -- phụ phí ùn tắc âm
  count(*) FILTER (WHERE airport_fee < 0) AS airport_am,              -- phí sân bay âm
  count(*) FILTER (WHERE cbd_congestion_fee < 0) AS cbd_am            -- phí ùn tắc khu trung tâm âm
FROM stage.stg_yellow_taxi_trips;   -- bảng staging
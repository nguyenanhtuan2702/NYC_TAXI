

-- (2) Tổng tiền không khớp tổng các khoản thành phần, theo payment_type.
-- Cột NULL (congestion, airport, cbd) được coi là 0. Sai lệch trên 0,01 USD mới tính.
-- Dòng có payment_type rỗng là tổng toàn bảng.
-- (2) KIEM TRA TOTAL_AMOUNT VA TONG CAC THANH PHAN
--
-- Kết quả đo ngày 18/11/2026 (24 tháng, ~90 triệu dòng): ~28,8 triệu dòng "không khớp", gần như
-- toàn bộ thuộc hai quy luật, không phải dữ liệu sai:
--   * payment_type = 0 (Flex Fare): cột phụ phí NULL nhưng total vẫn gồm phụ phí (lệch +2,50...).
--   * `extra` đã gồm sẵn phụ phí ùn tắc/CBD/sân bay nên công thức dưới cộng hai lần (lệch -2,50, -3,25...).
-- Cờ is_surcharge_missing và is_total_mismatch trong dbt/models/staging/stg_yellow_taxi_trips.sql
-- tính theo các quy luật này; còn ~384 nghìn dòng (0,43%) lệch thật.

WITH calculated AS (
    SELECT
        payment_type,
        total_amount,
        fare_amount
            + extra
            + mta_tax
            + tip_amount
            + tolls_amount
            + improvement_surcharge
            + COALESCE(congestion_surcharge, 0)
            + COALESCE(airport_fee, 0)
            + COALESCE(cbd_congestion_fee, 0)
            AS component_sum
    FROM raw.yellow_tripdata
)
SELECT
    payment_type,
    COUNT(*) AS so_dong,

    COUNT(*) FILTER (
        WHERE total_amount IS NULL
    ) AS total_null,

    COUNT(*) FILTER (
        WHERE component_sum IS NULL
    ) AS component_sum_null,

    COUNT(*) FILTER (
        WHERE total_amount IS NOT NULL
          AND component_sum IS NOT NULL
          AND ABS(total_amount - component_sum) > 0.01
    ) AS total_khong_khop,

    COUNT(*) FILTER (
        WHERE total_amount IS NOT NULL
          AND component_sum IS NOT NULL
          AND ABS(total_amount - component_sum) <= 0.01
    ) AS total_khop_trong_nguong

FROM calculated
GROUP BY payment_type
ORDER BY payment_type;


-- (3) Bảng Zone Lookup: số dòng, số mã khác nhau, mã nhỏ nhất, lớn nhất.
SELECT count(*) AS so_dong, count(DISTINCT location_id) AS so_ma,
       min(location_id) AS ma_nho_nhat, max(location_id) AS ma_lon_nhat
FROM raw.taxi_zone_lookup;

-- (4) Tên Zone bị trùng ở nhiều mã.
SELECT zone, count(*) AS so_dong,
       string_agg(location_id::text, ',' ORDER BY location_id) AS cac_ma
FROM raw.taxi_zone_lookup
GROUP BY zone
HAVING count(*) > 1
ORDER BY zone;


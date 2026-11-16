

-- (2) Tổng tiền không khớp tổng các khoản thành phần, theo payment_type.
-- Cột NULL (congestion, airport, cbd) được coi là 0. Sai lệch trên 0,01 USD mới tính.
-- Dòng có payment_type rỗng là tổng toàn bảng.
-- (2) KIEM TRA TOTAL_AMOUNT VA TONG CAC THANH PHAN

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
    FROM stage.stg_yellow_taxi_trips
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
FROM stage.stg_taxi_zone_lookup;

-- (4) Tên Zone bị trùng ở nhiều mã.
SELECT zone, count(*) AS so_dong,
       string_agg(location_id::text, ',' ORDER BY location_id) AS cac_ma
FROM stage.stg_taxi_zone_lookup
GROUP BY zone
HAVING count(*) > 1
ORDER BY zone;


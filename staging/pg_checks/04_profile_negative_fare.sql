
-- DOI CHIEU FARE AM VA TOTAL AM

SELECT
    payment_type,
    COUNT(*) AS so_dong,

    COUNT(*) FILTER (
        WHERE fare_amount < 0
    ) AS fare_am,

    COUNT(*) FILTER (
        WHERE total_amount < 0
    ) AS total_am,

    COUNT(*) FILTER (
        WHERE fare_amount < 0
          AND total_amount < 0
    ) AS ca_fare_va_total_am,

    COUNT(*) FILTER (
        WHERE fare_amount < 0
          AND total_amount >= 0
    ) AS fare_am_total_khong_am,

    COUNT(*) FILTER (
        WHERE fare_amount < 0
          AND total_amount IS NULL
    ) AS fare_am_total_null

FROM stage.stg_yellow_taxi_trips
GROUP BY payment_type
ORDER BY payment_type;

SELECT
  payment_type,
  count(*)                                                    AS so_dong,
  count(*) FILTER (WHERE fare_amount < 0)                     AS fare_am,
  count(*) FILTER (WHERE total_amount < 0)                    AS total_am,
  count(*) FILTER (WHERE fare_amount < 0 AND total_amount >= 0) AS fare_am_total_khong_am
FROM stage.stg_yellow_taxi_trips
GROUP BY payment_type
ORDER BY payment_type;
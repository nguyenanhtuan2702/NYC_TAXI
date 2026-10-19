SELECT
  vendor_id,
  count(*)                                              AS so_dong,
  count(*) FILTER (WHERE passenger_count IS NULL)       AS pax_null,
  count(*) FILTER (WHERE payment_type = 0)              AS pay_0,
  count(*) FILTER (WHERE ratecode_id IS NULL)           AS rate_null,
  count(*) FILTER (WHERE passenger_count IS NULL
                     AND payment_type = 0
                     AND ratecode_id IS NULL)           AS ca_ba_cung_luc,
  count(*) FILTER (WHERE fare_amount < 0)               AS fare_am,
  count(*) FILTER (WHERE total_amount < 0)              AS total_am
FROM stage.stg_yellow_taxi_trips
GROUP BY vendor_id
ORDER BY vendor_id;
SELECT
  count(*)                                                        AS tong_dong,
  count(*) FILTER (WHERE vendor_id IS NULL)                       AS vendor_null,
  count(*) FILTER (WHERE vendor_id NOT IN (1,2))                  AS vendor_la,
  count(*) FILTER (WHERE tpep_pickup_datetime IS NULL)            AS pickup_null,
  count(*) FILTER (WHERE tpep_dropoff_datetime IS NULL)           AS dropoff_null,
  count(*) FILTER (WHERE tpep_pickup_datetime < '2024-01-01'
                      OR tpep_pickup_datetime >= '2026-01-01')    AS pickup_ngoai_ky,
  count(*) FILTER (WHERE tpep_dropoff_datetime < tpep_pickup_datetime) AS dropoff_truoc_pickup,
  count(*) FILTER (WHERE passenger_count IS NULL)                 AS pax_null,
  count(*) FILTER (WHERE passenger_count = 0)                     AS pax_0,
  count(*) FILTER (WHERE trip_distance <= 0)                      AS dist_le_0,
  count(*) FILTER (WHERE fare_amount < 0)                         AS fare_am,
  count(*) FILTER (WHERE total_amount < 0)                        AS total_am,
  count(*) FILTER (WHERE pu_location_id NOT BETWEEN 1 AND 265
                      OR do_location_id NOT BETWEEN 1 AND 265)    AS location_ngoai_1_265,
  count(*) FILTER (WHERE pu_location_id IN (264,265)
                      OR do_location_id IN (264,265))             AS location_unknown,
  count(*) FILTER (WHERE ratecode_id = 99)                        AS ratecode_99,
  count(*) FILTER (WHERE ratecode_id IS NULL)                     AS ratecode_null,
  count(*) FILTER (WHERE payment_type = 0)                        AS payment_0,
  count(*) FILTER (WHERE payment_type IS NULL)                    AS payment_null
FROM stage.stg_yellow_taxi_trips;
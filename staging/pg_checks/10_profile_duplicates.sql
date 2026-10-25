-- XEM CÁC NHÓM DÒNG TRÙNG (nhóm lặp nhiều nhất lên đầu)
SELECT
  count(*) AS so_lan,                                        -- nhóm này lặp bao nhiêu lần
  array_agg(source_row_number ORDER BY source_row_number) AS cac_dong_trong_file,  -- số thứ tự các dòng trùng trong file
  vendor_id, tpep_pickup_datetime, tpep_dropoff_datetime, passenger_count,
  trip_distance, ratecode_id, store_and_fwd_flag, pu_location_id, do_location_id,
  payment_type, fare_amount, extra, mta_tax, tip_amount, tolls_amount,
  improvement_surcharge, total_amount, congestion_surcharge, airport_fee,
  cbd_congestion_fee
FROM stage.stg_yellow_taxi_trips
WHERE source_file_name = :'f'
GROUP BY vendor_id, tpep_pickup_datetime, tpep_dropoff_datetime, passenger_count,
         trip_distance, ratecode_id, store_and_fwd_flag, pu_location_id, do_location_id,
         payment_type, fare_amount, extra, mta_tax, tip_amount, tolls_amount,
         improvement_surcharge, total_amount, congestion_surcharge, airport_fee,
         cbd_congestion_fee
HAVING count(*) > 1
ORDER BY count(*) DESC;

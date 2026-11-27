-- Staging Yellow Taxi: giữ đủ mọi dòng của raw (không lọc), chuẩn hóa nhẹ,
-- thêm cột dẫn xuất và cờ chất lượng dữ liệu. Việc loại dòng do tầng DDS quyết định
-- (xem is_valid_for_fact). Quy tắc các cờ lấy từ truy vấn profiling trong sql/profiling/.
with src as (
    select * from {{ source('raw', 'yellow_tripdata') }}
),

typed as (
    select
        vendor_id,
        tpep_pickup_datetime,
        tpep_dropoff_datetime,
        passenger_count,
        trip_distance,
        ratecode_id,
        upper(trim(store_and_fwd_flag))                     as store_and_fwd_flag,
        pu_location_id,
        do_location_id,
        payment_type,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        improvement_surcharge,
        total_amount,
        congestion_surcharge,
        airport_fee,
        cbd_congestion_fee,

        -- cột kiểm toán
        source_file_name,
        source_row_number,
        batch_id,
        load_datetime,

        -- cột dẫn xuất
        strptime(regexp_extract(source_file_name, '(\d{4}-\d{2})', 1), '%Y-%m')::date
                                                            as source_month,
        date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) / 60.0
                                                            as trip_duration_minutes,
        fare_amount + extra + mta_tax + tip_amount + tolls_amount + improvement_surcharge
            + coalesce(congestion_surcharge, 0) + coalesce(airport_fee, 0)
            + coalesce(cbd_congestion_fee, 0)               as component_total_amount
    from src
)

select
    *,
    -- Cờ chất lượng. coalesce(..., false): cờ luôn là true/false, không NULL.
    coalesce(vendor_id is null or vendor_id not in (1, 2), false)
                                                            as is_vendor_unknown,
    coalesce(tpep_pickup_datetime < '2024-01-01'
             or tpep_pickup_datetime >= '2026-01-01', false) as is_pickup_out_of_period,
    coalesce(date_trunc('month', tpep_pickup_datetime)::date <> source_month, false)
                                                            as is_pickup_outside_source_month,
    coalesce(tpep_dropoff_datetime < tpep_pickup_datetime, false)
                                                            as is_dropoff_before_pickup,
    coalesce(tpep_dropoff_datetime = tpep_pickup_datetime, false)
                                                            as is_zero_duration,
    coalesce(trip_duration_minutes > 24 * 60, false)        as is_duration_over_24h,
    coalesce(passenger_count is null or passenger_count = 0, false)
                                                            as is_passenger_missing,
    coalesce(trip_distance <= 0, false)                     as is_distance_non_positive,
    coalesce(trip_duration_minutes > 0 and trip_distance > 0
             and trip_distance / (trip_duration_minutes / 60.0) > 100, false)
                                                            as is_speed_over_100mph,
    coalesce(fare_amount < 0 or total_amount < 0, false)    as is_negative_amount,
    -- Cột phụ phí NULL (gặp ở payment_type = 0, Flex Fare): total vẫn gồm phụ phí nhưng
    -- thành phần để trống, nên không kiểm tra được tổng tiền.
    congestion_surcharge is null                            as is_surcharge_missing,
    -- Tổng tiền không khớp. Đo trên dữ liệu 2024-2025: ở nhiều dòng `extra` đã gồm sẵn
    -- phụ phí ùn tắc, CBD và/hoặc sân bay, nên chấp nhận 4 cách tính:
    --   thành phần; trừ (ùn tắc + CBD); trừ sân bay; trừ cả ba.
    -- Đây là quy luật quan sát từ dữ liệu, không phải định nghĩa chính thức của TLC.
    coalesce(congestion_surcharge is not null
             and abs(total_amount - component_total_amount) > 0.01
             and abs(total_amount - (component_total_amount - congestion_surcharge
                                     - coalesce(cbd_congestion_fee, 0))) > 0.01
             and abs(total_amount - (component_total_amount - coalesce(airport_fee, 0))) > 0.01
             and abs(total_amount - (component_total_amount - coalesce(airport_fee, 0)
                                     - congestion_surcharge
                                     - coalesce(cbd_congestion_fee, 0))) > 0.01, false)
                                                            as is_total_mismatch,
    -- 264 'Unknown', 265 'Outside of NYC', hoặc mã ngoài danh mục 1-265
    coalesce(pu_location_id not between 1 and 263
             or do_location_id not between 1 and 263, false) as is_location_unknown,
    coalesce(payment_type = 0, false)                       as is_flex_fare,

    -- Điều kiện giữ dòng trong Fact (giống điều kiện WHERE hiện tại của fact_taxi_trips).
    coalesce(tpep_dropoff_datetime > tpep_pickup_datetime
             and tpep_pickup_datetime >= '2024-01-01'
             and tpep_pickup_datetime < '2026-01-01'
             and fare_amount >= 0
             and total_amount >= 0
             and trip_distance >= 0, false)                 as is_valid_for_fact
from typed

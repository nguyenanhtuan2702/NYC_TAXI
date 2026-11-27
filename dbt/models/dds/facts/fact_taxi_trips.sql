-- FactTaxiTrip: mỗi dòng là một chuyến đi hợp lệ (stg.is_valid_for_fact).
-- Incremental delete+insert theo file nguồn: lượt chạy sau chỉ lấy batch mới hơn batch lớn nhất
-- đã có trong Fact; nếu một file được nạp lại (batch mới), toàn bộ dòng cũ của file đó bị xóa rồi
-- chèn lại, nên Fact không bị trùng.
-- delete+insert chỉ xóa file có mặt trong lô mới, nên pre_hook dọn thêm các file đã bị xóa khỏi raw.
-- So với raw (~0,5 s) thay vì staging is_valid_for_fact (~49 s cho DELETE ... NOT IN trên view).
-- Trường hợp hiếm còn lại (nạp lại một file mà mọi dòng đều không hợp lệ) do test
-- assert_fact_matches_staging chặn: sửa bằng `dbt build --full-refresh -s fact_taxi_trips`.
{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='sourcefilename',
        schema='dds',
        alias='facttaxitrip',
        pre_hook="{% if is_incremental() %}
            delete from {{ this }} where sourcefilename not in (
                select distinct source_file_name from {{ source('raw', 'yellow_tripdata') }})
            {% endif %}"
    )
}}

-- Nhóm cự ly tra theo khoảng nửa mở [mốc dưới, mốc dưới của nhóm kế tiếp): không còn khe hở giữa
-- các nhóm như khi dùng BETWEEN min/max (1.9999 -> 2.0000, 5.0000 -> 5.0001). Kết quả giữ nguyên
-- với dữ liệu 2 chữ số thập phân (2.00 thuộc 2-5 miles, 5.00 thuộc 2-5 miles, 5.01 thuộc Over 5).
-- Mốc trên của nhóm cuối là 1e12 thay cho NULL: điều kiện `OR upper_bound IS NULL` làm DuckDB
-- không đẩy được bộ lọc incremental xuống trước join (bước Fact từ ~1 s lên ~50 s).
WITH distance_bounds AS (
    SELECT
        distancegroupsk,
        mindistance AS lower_bound,
        COALESCE(LEAD(mindistance) OVER (ORDER BY mindistance), 1e12) AS upper_bound
    FROM {{ ref('dim_distance_group') }}
    WHERE distancegroupsk > 0
)

SELECT
    COALESCE(d_pu.datesk, -1)                  AS pickupdatesk,
    COALESCE(d_do.datesk, -1)                  AS dropoffdatesk,
    COALESCE(t_pu.timesk, -1)                  AS pickuptimesk,
    COALESCE(t_do.timesk, -1)                  AS dropofftimesk,
    COALESCE(l_pu.locationsk, -1)              AS pickuplocationsk,
    COALESCE(l_do.locationsk, -1)              AS dropofflocationsk,
    COALESCE(v.vendorsk, -1)                   AS vendorsk,
    COALESCE(p.paymenttypesk, -1)              AS paymenttypesk,
    COALESCE(r.ratecodesk, -1)                 AS ratecodesk,
    COALESCE(pg.passengergroupsk, -1)          AS passengergroupsk,
    COALESCE(dg.distancegroupsk, -1)           AS distancegroupsk,

    stg.tpep_pickup_datetime                   AS pickupdatetime,
    stg.tpep_dropoff_datetime                  AS dropoffdatetime,

    1                                          AS totaltrips,
    COALESCE(stg.passenger_count, 0)           AS passengercount,
    stg.trip_distance                          AS tripdistance,
    ROUND(stg.trip_duration_minutes, 2)        AS tripdurationminutes,
    stg.fare_amount                            AS fareamount,
    COALESCE(stg.extra, 0)                     AS extra,
    COALESCE(stg.mta_tax, 0)                   AS mtatax,
    COALESCE(stg.tip_amount, 0)                AS tipamount,
    COALESCE(stg.tolls_amount, 0)              AS tollsamount,
    COALESCE(stg.improvement_surcharge, 0)     AS improvementsurcharge,
    COALESCE(stg.congestion_surcharge, 0)      AS congestionsurcharge,
    COALESCE(stg.airport_fee, 0)               AS airportfee,
    COALESCE(stg.cbd_congestion_fee, 0)        AS cbdcongestionfee,
    stg.total_amount                           AS totalamount,

    stg.source_file_name                       AS sourcefilename,
    stg.source_row_number                      AS sourcerownumber,
    stg.batch_id                               AS batchid,
    CURRENT_TIMESTAMP                          AS loadedat

FROM {{ ref('stg_yellow_taxi_trips') }} stg

LEFT JOIN {{ ref('dim_date') }} d_pu 
    ON d_pu.fulldate = stg.tpep_pickup_datetime::date
LEFT JOIN {{ ref('dim_date') }} d_do 
    ON d_do.fulldate = stg.tpep_dropoff_datetime::date

LEFT JOIN {{ ref('dim_time') }} t_pu 
    ON t_pu.hour = EXTRACT(HOUR FROM stg.tpep_pickup_datetime)::int 
   AND t_pu.minute = EXTRACT(MINUTE FROM stg.tpep_pickup_datetime)::int
LEFT JOIN {{ ref('dim_time') }} t_do 
    ON t_do.hour = EXTRACT(HOUR FROM stg.tpep_dropoff_datetime)::int 
   AND t_do.minute = EXTRACT(MINUTE FROM stg.tpep_dropoff_datetime)::int

-- DimLocation là SCD Type 2: chọn phiên bản có hiệu lực tại thời điểm đón (trả).
-- Dòng Fact đã nạp giữ nguyên SK phiên bản cũ khi khu vực đổi; chuyến nạp sau dùng phiên bản mới.
LEFT JOIN {{ ref('dim_location') }} l_pu 
    ON l_pu.locationid = stg.pu_location_id
   AND stg.tpep_pickup_datetime >= l_pu.validfrom
   AND stg.tpep_pickup_datetime <  l_pu.validto
LEFT JOIN {{ ref('dim_location') }} l_do 
    ON l_do.locationid = stg.do_location_id
   AND stg.tpep_dropoff_datetime >= l_do.validfrom
   AND stg.tpep_dropoff_datetime <  l_do.validto

LEFT JOIN {{ ref('dim_vendor') }} v 
    ON v.vendorid = stg.vendor_id

LEFT JOIN {{ ref('dim_payment_type') }} p 
    ON p.paymenttypeid = stg.payment_type

LEFT JOIN {{ ref('dim_rate_code') }} r 
    ON r.ratecodeid = COALESCE(stg.ratecode_id, 99)

LEFT JOIN {{ ref('dim_passenger_group') }} pg 
    ON COALESCE(stg.passenger_count, 0) BETWEEN pg.minpassengers AND pg.maxpassengers

LEFT JOIN distance_bounds dg
    ON stg.trip_distance >= dg.lower_bound
   AND stg.trip_distance < dg.upper_bound

-- Điều kiện giữ dòng định nghĩa một chỗ trong staging (stg_yellow_taxi_trips.is_valid_for_fact).
WHERE stg.is_valid_for_fact
{% if is_incremental() %}
  AND stg.batch_id > (SELECT COALESCE(MAX(batchid), 0) FROM {{ this }})
{% endif %}

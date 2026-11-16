{{
    config(
        materialized='incremental',
        schema='dds',
        alias='facttaxitrip'
    )
}}

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
    ROUND(EXTRACT(EPOCH FROM (stg.tpep_dropoff_datetime - stg.tpep_pickup_datetime)) / 60.0, 2) AS tripdurationminutes,
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

FROM {{ source('stage', 'stg_yellow_taxi_trips') }} stg

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

LEFT JOIN {{ ref('dim_location') }} l_pu 
    ON l_pu.locationid = stg.pu_location_id
LEFT JOIN {{ ref('dim_location') }} l_do 
    ON l_do.locationid = stg.do_location_id

LEFT JOIN {{ ref('dim_vendor') }} v 
    ON v.vendorid = stg.vendor_id

LEFT JOIN {{ ref('dim_payment_type') }} p 
    ON p.paymenttypeid = stg.payment_type

LEFT JOIN {{ ref('dim_rate_code') }} r 
    ON r.ratecodeid = COALESCE(stg.ratecode_id, 99)

LEFT JOIN {{ ref('dim_passenger_group') }} pg 
    ON stg.passenger_count BETWEEN pg.minpassengers AND pg.maxpassengers

LEFT JOIN {{ ref('dim_distance_group') }} dg 
    ON stg.trip_distance BETWEEN dg.mindistance AND dg.maxdistance

WHERE stg.tpep_dropoff_datetime > stg.tpep_pickup_datetime
  AND stg.tpep_pickup_datetime >= '2024-01-01'
  AND stg.tpep_pickup_datetime < '2026-01-01'
  AND stg.fare_amount >= 0
  AND stg.total_amount >= 0
  AND stg.trip_distance >= 0
{% if is_incremental() %}
  AND stg.batch_id > (SELECT COALESCE(MAX(batchid), 0) FROM {{ this }})
{% endif %}

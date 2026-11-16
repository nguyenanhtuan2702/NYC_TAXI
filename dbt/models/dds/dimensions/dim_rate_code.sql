-- DimRateCode: mã xuất hiện trong dữ liệu chuyến đi. NULL -> 99; 99 và mã lạ -> Unknown.
-- RateCodeSK = RateCodeID (ổn định).
{{ config(alias='dimratecode') }}

with codes as (
    select distinct coalesce(ratecode_id, 99)::int as ratecode_id
    from {{ source('stage', 'stg_yellow_taxi_trips') }}
)

select
    -1                        as ratecodesk,
    -1                        as ratecodeid,
    'Unknown'::varchar(50)    as ratecodename

union all

select
    ratecode_id,
    ratecode_id,
    (case ratecode_id
        when 1 then 'Standard rate'
        when 2 then 'JFK'
        when 3 then 'Newark'
        when 4 then 'Nassau or Westchester'
        when 5 then 'Negotiated fare'
        when 6 then 'Group ride'
        else 'Unknown'
    end)::varchar(50)
from codes
where ratecode_id <> -1

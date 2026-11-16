-- DimLocation: từ Taxi Zone Lookup. LocationSK = LocationID (ổn định).
{{ config(alias='dimlocation') }}

with zones as (
    select distinct on (location_id)
        location_id, borough, zone, service_zone
    from {{ source('stage', 'stg_taxi_zone_lookup') }}
    where location_id is not null
    order by location_id, load_datetime desc
)

select
    -1                        as locationsk,
    -1                        as locationid,
    'Unknown'::varchar(50)    as borough,
    'Unknown'::varchar(100)   as zone,
    'Unknown'::varchar(50)    as servicezone

union all

select
    location_id,
    location_id,
    borough::varchar(50),
    zone::varchar(100),
    service_zone::varchar(50)
from zones

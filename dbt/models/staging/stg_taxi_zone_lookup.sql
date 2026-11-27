-- Staging Taxi Zone Lookup: chuẩn hóa khoảng trắng, giữ nguyên giá trị nguồn
-- (kể cả 'N/A', 'Unknown'), thêm cờ khu vực không xác định.
with src as (
    select * from {{ source('raw', 'taxi_zone_lookup') }}
)

select
    location_id,
    trim(borough)                       as borough,
    trim(zone)                          as zone,
    trim(service_zone)                  as service_zone,
    location_id in (264, 265)           as is_unknown_zone,   -- 264 'Unknown', 265 'Outside of NYC'
    source_file_name,
    batch_id,
    load_datetime
from src

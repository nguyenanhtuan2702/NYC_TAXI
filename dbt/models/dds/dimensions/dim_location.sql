-- DimLocation: SCD Type 2 từ snapshot Taxi Zone Lookup (snap_taxi_zone_lookup).
-- Mỗi phiên bản của một LocationID là một dòng, có khoảng hiệu lực [ValidFrom, ValidTo).
-- LocationSK = LocationID * 100 + VersionNo (vd 132 phiên bản 1 -> 13201): số nguyên, ổn định
-- giữa các lần build, đọc được LocationID từ SK.
-- Phiên bản đầu tiên có ValidFrom = 1900-01-01: snapshot chỉ biết thời điểm chạy (không biết
-- khu vực có từ khi nào), nên coi phiên bản đầu tiên áp dụng cho mọi chuyến trước đó.
-- Fact tra khóa theo LocationID và thời điểm đón/trả nằm trong khoảng hiệu lực.
{{ config(alias='dimlocation') }}

with versions as (
    select
        location_id,
        borough,
        zone,
        service_zone,
        dbt_valid_from::timestamp                                   as dbt_valid_from,
        dbt_valid_to::timestamp                                     as dbt_valid_to,
        row_number() over (partition by location_id order by dbt_valid_from) as version_no
    from {{ ref('snap_taxi_zone_lookup') }}
    where location_id is not null
)

select
    -1                                  as locationsk,
    -1                                  as locationid,
    'Unknown'::varchar(50)              as borough,
    'Unknown'::varchar(100)             as zone,
    'Unknown'::varchar(50)              as servicezone,
    1                                   as versionno,
    timestamp '1900-01-01'              as validfrom,
    timestamp '9999-12-31'              as validto,
    true                                as iscurrent

union all

select
    location_id * 100 + version_no,
    location_id,
    borough::varchar(50),
    zone::varchar(100),
    service_zone::varchar(50),
    version_no,
    case when version_no = 1 then timestamp '1900-01-01' else dbt_valid_from end,
    coalesce(dbt_valid_to, timestamp '9999-12-31'),
    dbt_valid_to is null
from versions

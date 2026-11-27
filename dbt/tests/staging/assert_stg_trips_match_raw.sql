-- Staging không được lọc hay nhân bản dòng: số dòng theo từng file phải bằng raw.
-- PASS khi không trả về dòng nào.
with r as (
    select source_file_name, count(*) as raw_rows
    from {{ source('raw', 'yellow_tripdata') }}
    group by 1
),

s as (
    select source_file_name, count(*) as stg_rows
    from {{ ref('stg_yellow_taxi_trips') }}
    group by 1
)

select
    coalesce(r.source_file_name, s.source_file_name) as source_file_name,
    raw_rows,
    stg_rows
from r
full outer join s on r.source_file_name = s.source_file_name
where raw_rows is distinct from stg_rows

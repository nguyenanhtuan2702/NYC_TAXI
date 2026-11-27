-- Số dòng Fact theo từng file nguồn phải bằng số dòng staging có is_valid_for_fact.
-- Bắt được: file bị nạp trùng vào Fact, dòng hợp lệ bị mất do join, file thiếu trong Fact
-- (hoặc còn sót trong Fact khi đã bị xóa khỏi raw).
-- Test PASS khi truy vấn không trả về dòng nào.
with stg as (
    select source_file_name, count(*) as stg_rows
    from {{ ref('stg_yellow_taxi_trips') }}
    where is_valid_for_fact
    group by source_file_name
),

fct as (
    select sourcefilename as source_file_name, count(*) as fact_rows
    from {{ ref('fact_taxi_trips') }}
    group by sourcefilename
)

select
    coalesce(stg.source_file_name, fct.source_file_name) as source_file_name,
    coalesce(stg.stg_rows, 0)  as stg_rows,
    coalesce(fct.fact_rows, 0) as fact_rows
from stg
full outer join fct on fct.source_file_name = stg.source_file_name
where coalesce(stg.stg_rows, 0) <> coalesce(fct.fact_rows, 0)

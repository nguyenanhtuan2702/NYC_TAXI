-- DimDate: mỗi ngày 2024-01-01 .. 2026-01-31, cộng dòng Unknown (-1).
-- Chuyến đón trong 2024-2025 có thể trả khách sang 2026 (thực tế muộn nhất 2026-01-05),
-- nên kéo dài thêm tháng 01/2026 để DropoffDateSK không rơi vào Unknown.
-- DateSK = YYYYMMDD: ổn định giữa các lần build, Fact incremental không bị lệch khóa.
{{ config(alias='dimdate') }}

with days as (
    select d::date as full_date
    from generate_series(date '2024-01-01', date '2026-01-31', interval 1 day) as g(d)
)

select
    -1                        as datesk,
    '1900-01-01'::date        as fulldate,
    -1                        as day,
    -1                        as dayofweek,
    'Unknown'::varchar(20)    as dayname,
    -1                        as weekofyear,
    -1                        as month,
    'Unknown'::varchar(20)    as monthname,
    -1                        as quarter,
    -1                        as year

union all

select
    strftime(full_date, '%Y%m%d')::int,
    full_date,
    extract(day from full_date)::int,
    extract(isodow from full_date)::int,
    strftime(full_date, '%A')::varchar(20),
    extract(week from full_date)::int,
    extract(month from full_date)::int,
    strftime(full_date, '%B')::varchar(20),
    extract(quarter from full_date)::int,
    extract(year from full_date)::int
from days

-- DimDate: mỗi ngày 2024-01-01 .. 2025-12-31, cộng dòng Unknown (-1).
-- DateSK = YYYYMMDD: ổn định giữa các lần build, Fact incremental không bị lệch khóa.
{{ config(alias='dimdate') }}

with days as (
    select d::date as full_date
    from generate_series('2024-01-01'::date, '2025-12-31'::date, interval '1 day') as g(d)
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
    to_char(full_date, 'YYYYMMDD')::int,
    full_date,
    extract(day from full_date)::int,
    extract(isodow from full_date)::int,
    trim(to_char(full_date, 'Day'))::varchar(20),
    extract(week from full_date)::int,
    extract(month from full_date)::int,
    trim(to_char(full_date, 'Month'))::varchar(20),
    extract(quarter from full_date)::int,
    extract(year from full_date)::int
from days

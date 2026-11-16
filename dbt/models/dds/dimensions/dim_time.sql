-- DimTime: 24 x 60 phút, cộng dòng Unknown (-1).
-- TimeSK = hour * 100 + minute (vd 13:45 -> 1345).
{{ config(alias='dimtime') }}

with minutes as (
    select h, m
    from generate_series(0, 23) as h, generate_series(0, 59) as m
)

select
    -1                        as timesk,
    -1                        as hour,
    -1                        as minute,
    'Unknown'::varchar(20)    as timeofday,
    'Unknown'::varchar(50)    as timeslot

union all

select
    h * 100 + m,
    h,
    m,
    (case
        when h >= 5  and h < 12 then 'Morning'
        when h >= 12 and h < 17 then 'Afternoon'
        when h >= 17 and h < 21 then 'Evening'
        else 'Night'
    end)::varchar(20),
    (lpad(h::text, 2, '0') || ':00 - ' || lpad((h + 1)::text, 2, '0') || ':00')::varchar(50)
from minutes

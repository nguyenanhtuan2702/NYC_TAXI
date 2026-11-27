-- Tuyến (khu vực đón → khu vực trả) theo tháng đón.
-- Phục vụ A7 (Top N tuyến phổ biến, slice theo thời gian) và B5 (lượt đón/trả theo Taxi Zone để
-- vẽ bản đồ: cộng theo pickup_locationid hoặc dropoff_locationid; nối với Taxi Zone Boundaries
-- qua LocationID ở bước Power BI).
select
    d.year,
    d.month,
    f.pickuplocationsk      as pickup_locationsk,
    lp.locationid           as pickup_locationid,
    lp.borough              as pickup_borough,
    lp.zone                 as pickup_zone,
    f.dropofflocationsk     as dropoff_locationsk,
    ld.locationid           as dropoff_locationid,
    ld.borough              as dropoff_borough,
    ld.zone                 as dropoff_zone,
    {{ olap_trip_measures('f') }}
from {{ ref('fact_taxi_trips') }} f
left join {{ ref('dim_date') }}     d  on d.datesk = f.pickupdatesk
left join {{ ref('dim_location') }} lp on lp.locationsk = f.pickuplocationsk
left join {{ ref('dim_location') }} ld on ld.locationsk = f.dropofflocationsk
group by all

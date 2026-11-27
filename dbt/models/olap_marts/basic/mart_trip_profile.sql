-- Hồ sơ chuyến đi theo tháng: nhóm hành khách × mã giá × nhóm cự ly × hình thức thanh toán.
-- Phục vụ A5 (số chuyến theo nhóm khách, mã giá, nhóm cự ly), B1 (tỷ lệ boa và vận tốc trung
-- bình theo mã giá), B3 (biến động theo mã giá, nhóm cự ly).
select
    d.year,
    d.month,
    f.passengergroupsk,
    pg.passengergroupcode,
    pg.passengergroupname,
    f.ratecodesk,
    r.ratecodename,
    f.distancegroupsk,
    dg.distancegroupcode,
    dg.distancegroupname,
    f.paymenttypesk,
    p.paymenttypename,
    {{ olap_trip_measures('f') }}
from {{ ref('fact_taxi_trips') }} f
left join {{ ref('dim_date') }}            d  on d.datesk = f.pickupdatesk
left join {{ ref('dim_passenger_group') }} pg on pg.passengergroupsk = f.passengergroupsk
left join {{ ref('dim_rate_code') }}       r  on r.ratecodesk = f.ratecodesk
left join {{ ref('dim_distance_group') }}  dg on dg.distancegroupsk = f.distancegroupsk
left join {{ ref('dim_payment_type') }}    p  on p.paymenttypesk = f.paymenttypesk
group by all

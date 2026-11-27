-- Mart chính: ngày đón × khu vực đón × hãng xe × hình thức thanh toán × mã giá.
-- Phục vụ A1 (chuyến, hành khách theo ngày → tháng → năm), A2 (doanh thu theo quận/zone × hãng xe
-- × ngày/tháng/năm), A3 (chuyến theo thanh toán × quận × tháng), A6 (dashboard theo quận),
-- A8 (tổng doanh thu), B2/B3 (phân tích biến động doanh thu theo hãng, khu vực, mã giá, các khoản phí).
-- Thuộc tính khu vực là phiên bản (SCD2) có hiệu lực tại thời điểm đón.
select
    f.pickupdatesk          as datesk,
    d.fulldate,
    d.year,
    d.quarter,
    d.month,
    d.monthname,
    d.weekofyear,
    d.day,
    d.dayofweek,
    d.dayname,
    f.pickuplocationsk      as locationsk,
    l.locationid,
    l.borough,
    l.zone,
    l.servicezone,
    f.vendorsk,
    v.vendorname,
    f.paymenttypesk,
    p.paymenttypename,
    f.ratecodesk,
    r.ratecodename,
    {{ olap_trip_measures('f') }}
from {{ ref('fact_taxi_trips') }} f
left join {{ ref('dim_date') }}         d on d.datesk = f.pickupdatesk
left join {{ ref('dim_location') }}     l on l.locationsk = f.pickuplocationsk
left join {{ ref('dim_vendor') }}       v on v.vendorsk = f.vendorsk
left join {{ ref('dim_payment_type') }} p on p.paymenttypesk = f.paymenttypesk
left join {{ ref('dim_rate_code') }}    r on r.ratecodesk = f.ratecodesk
group by all

-- KPI theo tháng đón và tốc độ tăng trưởng.
-- Phục vụ B2 (tháng 5 so với tháng 6), B3 (doanh thu tăng nhưng số chuyến gần như không đổi:
-- so sánh doanh thu/chuyến, quãng đường/chuyến, các khoản phí/chuyến), B4 (so sánh cùng kỳ năm trước).
-- Tháng trước / cùng kỳ năm trước tìm bằng phép nối theo ngày đầu tháng (không dùng lag) để
-- tháng thiếu dữ liệu không làm lệch kỳ so sánh.
with monthly as (
    select
        make_date(d.year, d.month, 1)   as month_start,
        d.year,
        d.month,
        d.monthname,
        {{ olap_trip_measures('f') }}
    from {{ ref('fact_taxi_trips') }} f
    join {{ ref('dim_date') }} d on d.datesk = f.pickupdatesk
    group by all
),

kpi as (
    select
        *,
        total_revenue / nullif(total_trips, 0)                  as avg_revenue_per_trip,
        fare_amount / nullif(total_trips, 0)                    as avg_fare_per_trip,
        (extra + mta_tax + improvement_surcharge + congestion_surcharge
            + airport_fee + cbd_congestion_fee) / nullif(total_trips, 0)
                                                                as avg_surcharges_per_trip,
        tip_amount / nullif(total_trips, 0)                     as avg_tip_per_trip,
        total_distance / nullif(valid_distance_trips, 0)        as avg_distance_per_trip,
        total_duration_minutes / nullif(valid_duration_trips, 0) as avg_duration_minutes,
        total_passengers / nullif(valid_passenger_trips, 0)     as avg_passengers_per_trip,
        sum_trip_speed / nullif(valid_speed_trips, 0)           as avg_speed_mph,
        credit_tip_amount / nullif(credit_fare_amount, 0)       as avg_tip_rate
    from monthly
)

select
    cur.*,
    prev.total_trips                                            as prev_month_trips,
    prev.total_revenue                                          as prev_month_revenue,
    (cur.total_trips - prev.total_trips) / nullif(prev.total_trips, 0)       as trip_growth_mom,
    (cur.total_revenue - prev.total_revenue) / nullif(prev.total_revenue, 0) as revenue_growth_mom,
    ly.total_trips                                              as same_month_ly_trips,
    ly.total_revenue                                            as same_month_ly_revenue,
    (cur.total_trips - ly.total_trips) / nullif(ly.total_trips, 0)           as trip_growth_yoy,
    (cur.total_revenue - ly.total_revenue) / nullif(ly.total_revenue, 0)     as revenue_growth_yoy
from kpi cur
left join kpi prev on prev.month_start = cur.month_start - interval 1 month
left join kpi ly   on ly.month_start   = cur.month_start - interval 1 year

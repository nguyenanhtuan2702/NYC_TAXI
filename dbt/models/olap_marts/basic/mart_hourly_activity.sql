-- Lượt đón và lượt trả theo ngày × giờ × quận, hai vai trò trong cùng một bảng (activity_role).
-- Phục vụ A4 (đón/trả theo giờ, khung giờ, thứ, tháng), A2 ở mức giờ, 5b (doanh thu quận × tháng
-- × khung giờ: dùng activity_role = 'pickup').
-- Doanh thu (total_revenue) gắn với chuyến; khi cộng, chỉ lấy MỘT vai trò để không tính hai lần.
with pickup as (
    select
        'pickup'                as activity_role,
        f.pickupdatesk          as datesk,
        f.pickuptimesk          as timesk,
        f.pickuplocationsk      as locationsk,
        f.totaltrips,
        f.passengercount,
        f.totalamount
    from {{ ref('fact_taxi_trips') }} f
),

dropoff as (
    select
        'dropoff',
        f.dropoffdatesk,
        f.dropofftimesk,
        f.dropofflocationsk,
        f.totaltrips,
        f.passengercount,
        f.totalamount
    from {{ ref('fact_taxi_trips') }} f
),

events as (
    select * from pickup
    union all
    select * from dropoff
)

select
    e.activity_role,
    e.datesk,
    d.fulldate,
    d.year,
    d.month,
    d.monthname,
    d.dayofweek,
    d.dayname,
    t.hour,
    t.timeofday,
    t.timeslot,
    l.borough,
    sum(e.totaltrips)::bigint     as total_trips,
    sum(e.passengercount)::bigint as total_passengers,
    sum(e.totalamount)      as total_revenue
from events e
left join {{ ref('dim_date') }}     d on d.datesk = e.datesk
left join {{ ref('dim_time') }}     t on t.timesk = e.timesk
left join {{ ref('dim_location') }} l on l.locationsk = e.locationsk
group by all

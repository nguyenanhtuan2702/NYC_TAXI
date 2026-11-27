-- Mỗi OLAP mart phải giữ đúng tổng số chuyến, hành khách và doanh thu của Fact
-- (mart chỉ gộp nhóm, không được mất hay nhân dòng). mart_hourly_activity kiểm tra riêng từng vai trò.
-- Doanh thu là số thực cộng theo thứ tự khác nhau nên cho phép lệch dưới 1 USD trên ~2 tỷ USD.
-- Test PASS khi truy vấn không trả về dòng nào.
with fact as (
    select sum(totaltrips) as trips, sum(passengercount) as passengers, sum(totalamount) as revenue
    from {{ ref('fact_taxi_trips') }}
),

marts as (
    select 'mart_trips_daily' as mart, sum(total_trips) as trips, sum(total_passengers) as passengers,
           sum(total_revenue) as revenue
    from {{ ref('mart_trips_daily') }}
    union all
    select 'mart_routes_monthly', sum(total_trips), sum(total_passengers), sum(total_revenue)
    from {{ ref('mart_routes_monthly') }}
    union all
    select 'mart_trip_profile', sum(total_trips), sum(total_passengers), sum(total_revenue)
    from {{ ref('mart_trip_profile') }}
    union all
    select 'mart_monthly_kpi', sum(total_trips), sum(total_passengers), sum(total_revenue)
    from {{ ref('mart_monthly_kpi') }}
    union all
    select 'mart_hourly_activity:' || activity_role, sum(total_trips), sum(total_passengers),
           sum(total_revenue)
    from {{ ref('mart_hourly_activity') }}
    group by activity_role
)

select
    m.mart,
    m.trips, f.trips as fact_trips,
    m.passengers, f.passengers as fact_passengers,
    m.revenue, f.revenue as fact_revenue
from marts m
cross join fact f
where m.trips <> f.trips
   or m.passengers <> f.passengers
   or abs(m.revenue - f.revenue) >= 1
-- Thiếu hẳn một vai trò trong mart_hourly_activity cũng là lỗi.
union all
select 'mart_hourly_activity: thiếu vai trò', null, null, null, null, null, null
from {{ ref('mart_hourly_activity') }}
having count(distinct activity_role) <> 2

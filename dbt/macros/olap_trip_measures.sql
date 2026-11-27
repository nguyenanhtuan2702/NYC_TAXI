{#
  Bộ measure dùng chung cho các OLAP mart (cộng dồn được), theo modeling.pdf mục 4.
  Các measure trung bình (AvgSpeed, AvgTipRate, AvgDistancePerTrip, ...) KHÔNG lưu sẵn vì
  không cộng dồn được; BI tính lại từ tổng và số chuyến hợp lệ tương ứng, ví dụ:
    AvgDistancePerTrip = total_distance / valid_distance_trips
    AvgSpeed (trung bình từng chuyến) = sum_trip_speed / valid_speed_trips
    AvgTipRate (tổng thể, B1)         = credit_tip_amount / credit_fare_amount
  Tham số f: alias của bảng Fact trong câu truy vấn gọi macro.
  Tổng số nguyên ép về BIGINT: sum(int) của DuckDB trả HUGEINT (int128), Power BI/ODBC không đọc được.
#}
{% macro olap_trip_measures(f) -%}
    sum({{ f }}.totaltrips)::bigint                                      as total_trips,
    sum({{ f }}.passengercount)::bigint                                  as total_passengers,
    count(*) filter (where {{ f }}.passengercount > 0)                   as valid_passenger_trips,
    sum({{ f }}.tripdistance)                                            as total_distance,
    count(*) filter (where {{ f }}.tripdistance > 0)                     as valid_distance_trips,
    sum({{ f }}.tripdurationminutes)                                     as total_duration_minutes,
    count(*) filter (where {{ f }}.tripdurationminutes > 0)              as valid_duration_trips,
    -- Vận tốc hợp lệ: quãng đường và thời lượng dương, không quá 100 mph (cùng ngưỡng cờ staging).
    count(*) filter (where {{ olap_valid_speed(f) }})                    as valid_speed_trips,
    sum({{ f }}.tripdistance / ({{ f }}.tripdurationminutes / 60.0))
        filter (where {{ olap_valid_speed(f) }})                         as sum_trip_speed,
    -- Tỷ lệ boa chỉ tính cho thẻ tín dụng (tiền mặt không ghi nhận boa) và cước dương.
    count(*) filter (where {{ olap_valid_tip(f) }})                      as valid_tip_rate_trips,
    sum({{ f }}.tipamount / {{ f }}.fareamount)
        filter (where {{ olap_valid_tip(f) }})                           as sum_trip_tip_rate,
    sum({{ f }}.tipamount)  filter (where {{ olap_valid_tip(f) }})       as credit_tip_amount,
    sum({{ f }}.fareamount) filter (where {{ olap_valid_tip(f) }})       as credit_fare_amount,
    sum({{ f }}.fareamount)                                              as fare_amount,
    sum({{ f }}.extra)                                                   as extra,
    sum({{ f }}.mtatax)                                                  as mta_tax,
    sum({{ f }}.tipamount)                                               as tip_amount,
    sum({{ f }}.tollsamount)                                             as tolls_amount,
    sum({{ f }}.improvementsurcharge)                                    as improvement_surcharge,
    sum({{ f }}.congestionsurcharge)                                     as congestion_surcharge,
    sum({{ f }}.airportfee)                                              as airport_fee,
    sum({{ f }}.cbdcongestionfee)                                        as cbd_congestion_fee,
    sum({{ f }}.totalamount)                                             as total_revenue
{%- endmacro %}

{% macro olap_valid_speed(f) -%}
    {{ f }}.tripdistance > 0 and {{ f }}.tripdurationminutes > 0
    and {{ f }}.tripdistance / ({{ f }}.tripdurationminutes / 60.0) <= 100
{%- endmacro %}

{% macro olap_valid_tip(f) -%}
    {{ f }}.paymenttypesk = 1 and {{ f }}.fareamount > 0
{%- endmacro %}

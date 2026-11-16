-- Mỗi Dimension phải có đúng một dòng Unknown (SK = -1) để Fact gán khóa mồ côi.
-- Test PASS khi truy vấn không trả về dòng nào.
{% set dims = [
    ('dim_date', 'datesk'), ('dim_time', 'timesk'), ('dim_location', 'locationsk'),
    ('dim_vendor', 'vendorsk'), ('dim_payment_type', 'paymenttypesk'),
    ('dim_rate_code', 'ratecodesk'), ('dim_passenger_group', 'passengergroupsk'),
    ('dim_distance_group', 'distancegroupsk')
] %}

{% for model, sk in dims %}
select '{{ model }}' as dimension, count(*) as unknown_rows
from {{ ref(model) }}
where {{ sk }} = -1
having count(*) <> 1
{% if not loop.last %}union all{% endif %}
{% endfor %}

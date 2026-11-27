-- DimPassengerGroup: nhóm tĩnh theo số hành khách. Nhãn tiếng Anh (hiển thị trên dashboard Power BI).
-- NONE: passenger_count = 0 hoặc NULL (Fact join bằng coalesce(passenger_count, 0)); chủ yếu chuyến Flex Fare.
{{ config(alias='dimpassengergroup') }}

select
    g.passengergroupsk,
    g.passengergroupcode::varchar(20)  as passengergroupcode,
    g.passengergroupname::varchar(50)  as passengergroupname,
    g.minpassengers,
    g.maxpassengers
from (values
    (-1, 'UNK',    'Unknown',                 -1,   -1),
    ( 0, 'NONE',   'No passenger count',        0,    0),
    ( 1, 'SINGLE', '1 passenger',               1,    1),
    ( 2, 'SMALL',  '2-4 passengers',            2,    4),
    ( 3, 'LARGE',  '5+ passengers',             5, 9999)
) as g(passengergroupsk, passengergroupcode, passengergroupname, minpassengers, maxpassengers)

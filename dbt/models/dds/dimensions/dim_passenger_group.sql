-- DimPassengerGroup: nhóm tĩnh theo số hành khách.
{{ config(alias='dimpassengergroup') }}

select
    g.passengergroupsk,
    g.passengergroupcode::varchar(20)  as passengergroupcode,
    g.passengergroupname::varchar(50)  as passengergroupname,
    g.minpassengers,
    g.maxpassengers
from (values
    (-1, 'UNK',    'Unknown',                 -1,   -1),
    ( 1, 'SINGLE', '1 hành khách',              1,    1),
    ( 2, 'SMALL',  'Nhóm 2-4 người',            2,    4),
    ( 3, 'LARGE',  'Nhóm từ 5 người trở lên',   5, 9999)
) as g(passengergroupsk, passengergroupcode, passengergroupname, minpassengers, maxpassengers)

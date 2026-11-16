-- DimDistanceGroup: nhóm tĩnh theo quãng đường (miles), dải liên tục, NUMERIC(10,4).
{{ config(alias='dimdistancegroup') }}

select
    g.distancegroupsk,
    g.distancegroupcode::varchar(20)  as distancegroupcode,
    g.distancegroupname::varchar(50)  as distancegroupname,
    g.mindistance::numeric(10, 4)     as mindistance,
    g.maxdistance::numeric(10, 4)     as maxdistance
from (values
    (-1, 'UNK',    'Unknown',          -1,          -1),
    ( 1, 'SHORT',  'Dưới 2 miles',      0.0000,      1.9999),
    ( 2, 'MEDIUM', '2 đến 5 miles',     2.0000,      5.0000),
    ( 3, 'LONG',   'Trên 5 miles',      5.0001, 999999.9999)
) as g(distancegroupsk, distancegroupcode, distancegroupname, mindistance, maxdistance)

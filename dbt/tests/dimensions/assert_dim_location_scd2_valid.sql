-- Kiểm tra tính hợp lệ của DimLocation (SCD Type 2). Mỗi LocationID phải có:
--   1. đúng một phiên bản hiện hành (IsCurrent) và phiên bản đó có ValidTo = 9999-12-31;
--   2. các phiên bản nối liền, không chồng lấn: ValidTo của phiên bản trước = ValidFrom của phiên bản sau;
--   3. phiên bản đầu tiên bắt đầu từ 1900-01-01 (phủ mọi chuyến đi trong quá khứ);
--   4. VersionNo liên tục 1..N.
-- Test PASS khi truy vấn không trả về dòng nào.
with v as (
    select
        locationid,
        versionno,
        validfrom,
        validto,
        iscurrent,
        lead(validfrom) over (partition by locationid order by versionno)   as next_validfrom,
        row_number() over (partition by locationid order by validfrom)      as expected_versionno
    from {{ ref('dim_location') }}
)

select locationid, 'số phiên bản hiện hành khác 1' as loi
from v
group by locationid
having count(*) filter (where iscurrent) <> 1

union all
select locationid, 'phiên bản hiện hành có ValidTo khác 9999-12-31'
from v
where iscurrent and validto <> timestamp '9999-12-31'

union all
select locationid, 'phiên bản không nối liền hoặc chồng lấn'
from v
where next_validfrom is not null and next_validfrom <> validto

union all
select locationid, 'phiên bản đầu tiên không bắt đầu từ 1900-01-01'
from v
where versionno = 1 and validfrom <> timestamp '1900-01-01'

union all
select locationid, 'VersionNo không liên tục'
from v
where versionno <> expected_versionno

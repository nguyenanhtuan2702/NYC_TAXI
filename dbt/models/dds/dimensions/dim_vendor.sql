-- DimVendor: mã xuất hiện trong dữ liệu chuyến đi. Mã ngoài 1/2 (vd 6, 7) -> Unknown.
-- VendorSK = VendorID (ổn định).
{{ config(alias='dimvendor') }}

with codes as (
    select distinct vendor_id
    from {{ ref('stg_yellow_taxi_trips') }}
    where vendor_id is not null
)

select
    -1                        as vendorsk,
    -1                        as vendorid,
    'Unknown'::varchar(50)    as vendorname

union all

select
    vendor_id,
    vendor_id,
    (case vendor_id
        when 1 then 'Creative Mobile Technologies'
        when 2 then 'VeriFone Inc.'
        else 'Unknown'
    end)::varchar(50)
from codes
where vendor_id <> -1

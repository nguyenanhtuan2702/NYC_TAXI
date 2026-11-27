-- DimPaymentType: mã xuất hiện trong dữ liệu chuyến đi. Mã 0 (Flex Fare) và mã lạ -> Unknown.
-- PaymentTypeSK = PaymentTypeID (ổn định).
{{ config(alias='dimpaymenttype') }}

with codes as (
    select distinct payment_type::int as payment_type
    from {{ ref('stg_yellow_taxi_trips') }}
    where payment_type is not null
)

select
    -1                        as paymenttypesk,
    -1                        as paymenttypeid,
    'Unknown'::varchar(50)    as paymenttypename

union all

select
    payment_type,
    payment_type,
    (case payment_type
        when 1 then 'Credit card'
        when 2 then 'Cash'
        when 3 then 'No charge'
        when 4 then 'Dispute'
        when 5 then 'Unknown'
        when 6 then 'Voided trip'
        else 'Unknown'
    end)::varchar(50)
from codes
where payment_type <> -1

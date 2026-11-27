# Dimension (DDS)

8 bảng Dimension của Star Schema, build bằng dbt-duckdb trong schema `dds` của file DuckDB. Model ở `dbt/models/dds/dimensions/`, đọc staging qua `ref()` (xem [staging.md](staging.md)). Thiết kế theo `docs/data_modeling/modeling.pdf`.

## Chạy

```powershell
.\tasks.ps1 dbt-build dds.dimensions    # 8 bảng + test
.\tasks.ps1 dbt-build                   # toàn bộ (gồm snapshot SCD2 mà dim_location cần)
```

Mỗi Dimension là `materialized: table`: mỗi lần build tạo lại bảng, nên chạy lặp luôn cho cùng kết quả. `dim_location` đọc snapshot `snapshots.snap_taxi_zone_lookup`; nếu chỉ build `dds.dimensions` thì snapshot phải đã tồn tại (đã chạy `dbt build` toàn bộ hoặc `dbt snapshot` ít nhất một lần).

## Các bảng

| Model | Bảng | Surrogate key | Nguồn |
|---|---|---|---|
| `dim_date` | `dds.dimdate` | `YYYYMMDD` | sinh 2024-01-01 → 2026-01-31 |
| `dim_time` | `dds.dimtime` | `hour*100 + minute` | sinh 24 × 60 phút |
| `dim_location` | `dds.dimlocation` | `LocationID*100 + VersionNo` | snapshot Zone Lookup (SCD Type 2) |
| `dim_vendor` | `dds.dimvendor` | = `VendorID` | mã có trong chuyến đi; ngoài 1/2 → nhãn Unknown |
| `dim_payment_type` | `dds.dimpaymenttype` | = `PaymentTypeID` | mã có trong chuyến đi; mã 0 → nhãn Unknown |
| `dim_rate_code` | `dds.dimratecode` | = `RateCodeID` | mã có trong chuyến đi; NULL → 99 Unknown |
| `dim_passenger_group` | `dds.dimpassengergroup` | 0..3 | tĩnh |
| `dim_distance_group` | `dds.dimdistancegroup` | 1..3 | tĩnh |

**SK sinh ổn định từ khóa tự nhiên**, không dùng số tự tăng. Nhờ vậy build lại Dimension không làm lệch khóa của các dòng Fact đã nạp incremental.

Nhãn hiển thị (tên nhóm, tên hãng...) bằng tiếng Anh vì dashboard dùng tiếng Anh.

### Nhóm tĩnh

| Bảng | Nhóm | Khoảng |
|---|---|---|
| `dimpassengergroup` | `NONE` (SK 0) | `passenger_count` NULL hoặc 0 (chủ yếu chuyến Flex Fare); Fact join bằng `coalesce(passenger_count, 0)` |
| | `SINGLE` (1), `SMALL` (2), `LARGE` (3) | 1; 2–4; 5–9999 |
| `dimdistancegroup` | `SHORT` (1), `MEDIUM` (2), `LONG` (3) | `mindistance` 0 / 2 / 5,0001 (miles, `NUMERIC(10,4)`) |

Fact tra nhóm cự ly theo khoảng nửa mở `[mindistance, mindistance của nhóm kế tiếp)`, không dùng `BETWEEN mindistance AND maxdistance`, nên không có khe hở giữa 1,9999 và 2,0 hay 5,0 và 5,0001. Cột `maxdistance` chỉ để hiển thị.

`DimDate` chạy tới 2026-01-31 vì 759 chuyến đón cuối 2025 trả khách trong tháng 01/2026 (muộn nhất 05/01/2026). Không có chuyến nào **đón** trong năm 2026.

## Hai lớp Unknown

**Lớp 1, mã có thật nhưng ngoài danh mục.** Giá trị tồn tại trong nguồn nhưng không thuộc danh mục TLC (ví dụ `vendor_id` 6, 7; `payment_type` 0) vẫn có một dòng Dimension với mã gốc, chỉ có tên chuẩn hóa thành `Unknown`. Fact join bình thường theo mã.

```sql
case vendor_id
    when 1 then 'Creative Mobile Technologies'
    when 2 then 'VeriFone Inc.'
    else 'Unknown'
end as vendorname
```

**Lớp 2, dòng SK = -1.** Mọi Dimension có một dòng `SK = -1` (`Unknown`). Fact dùng `LEFT JOIN` + `COALESCE(sk, -1)`, nên chuyến đi có mã không khớp Dimension nào vẫn được giữ, không mất doanh thu. Test `assert_unknown_member_exists` kiểm tra dòng này ở cả 8 bảng.

Hiện tại Fact có **0 dòng mang khóa -1** ở cả 11 khóa.

## DimLocation: SCD Type 2

- **Nguồn:** snapshot `snapshots.snap_taxi_zone_lookup` (`dbt/snapshots/snap_taxi_zone_lookup.yml`, `strategy: check` trên `borough`, `zone`, `service_zone`).
- **Mỗi phiên bản một dòng:** `LocationSK = LocationID*100 + VersionNo` (vd 13201), `ValidFrom` (phiên bản 1 = 1900-01-01), `ValidTo` (hiện hành = 9999-12-31), `IsCurrent`.
- **Fact tra khóa** theo `LocationID` và giờ đón/trả nằm trong `[ValidFrom, ValidTo)`. Khi khu vực đổi tên, chuyến đã nạp vẫn giữ phiên bản cũ.
- **Giới hạn:** `ValidFrom` của phiên bản mới là thời điểm chạy snapshot, không phải ngày TLC đổi khu vực (nguồn không có ngày hiệu lực).
- **Test:** `dbt/tests/dimensions/assert_dim_location_scd2_valid.sql` (một bản hiện hành mỗi `LocationID`, các phiên bản nối liền nhau).

## Kết quả (18/11/2026, 24 tháng)

| Bảng | Số dòng |
|---|---:|
| `dimdate` | 763 (762 ngày + Unknown) |
| `dimtime` | 1.441 |
| `dimlocation` | 266 |
| `dimvendor` | 5 |
| `dimpaymenttype` | 7 |
| `dimratecode` | 8 |
| `dimpassengergroup` | 5 |
| `dimdistancegroup` | 4 |

Mọi test PASS. Đo trên DuckDB, mỗi Dimension đọc `SELECT DISTINCT` từ staging mất 0,6–1,6 s.

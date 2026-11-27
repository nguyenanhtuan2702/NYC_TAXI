# Ingestion: Source → DuckDB (`raw`)

Bước đầu của pipeline: lấy dữ liệu nguồn và nạp nguyên trạng vào DuckDB. Làm sạch và đổi kiểu dữ liệu thuộc tầng staging (dbt), không làm ở đây.

## Nguồn và đích

| Nguồn | Pipeline Mage | Bảng đích |
|---|---|---|
| `data/reference/taxi_zone_lookup.csv` (265 khu vực) | `ingest_zone_lookup` | `raw.taxi_zone_lookup` |
| Yellow Taxi Parquet theo tháng, 2024-01 → 2025-12, tải từ `https://d37ci6vzurychx.cloudfront.net/trip-data/` | `ingest_yellow_trips` | `raw.yellow_tripdata` |
| (mọi lần nạp) | cả hai | `control.etl_control` |

File DuckDB: `data/warehouse/nyc_taxi.duckdb` (trong container: `/home/src/data/warehouse/nyc_taxi.duckdb`). DDL ở `sql/ddl/`; mỗi lần chạy, block nạp tự chạy các file này (đều `IF NOT EXISTS`), nên không cần tạo bảng thủ công.

## Chạy

Container phải đang chạy (`.\tasks.ps1 up`).

```powershell
.\tasks.ps1 ingest-zones                                   # Zone Lookup
.\tasks.ps1 ingest yellow_tripdata_2024-01.parquet         # một tháng
.\tasks.ps1 ingest                                         # ALL: mọi tháng chưa nạp thành công
.\tasks.ps1 ingest '{"file_name":"ALL","year":2024}'       # theo năm
.\tasks.ps1 ingest '{"file_name":"ALL","start_month":"2024-03","end_month":"2024-06"}'
.\tasks.ps1 ingest '{"file_name":"ALL","use_lset":true}'   # bắt đầu từ LSET
```

Hoặc trên giao diện Mage (<http://localhost:6789>): mở pipeline, chỉnh biến, bấm ▶ ở block cuối. Đổi biến trên giao diện sẽ sửa `mage/pipelines/*/metadata.yaml`; không commit thay đổi đó.

### Biến của `ingest_yellow_trips`

| Biến | Ví dụ | Ý nghĩa |
|---|---|---|
| `file_name` | `yellow_tripdata_2024-01.parquet` | Chỉ nạp file này (luôn nạp lại, kể cả đã SUCCESS) |
| `file_name` | `ALL` (mặc định) | Xét các tháng 2024–2025, bỏ qua file đã SUCCESS |
| `year` | `2024` | Chỉ xét một năm |
| `start_month`, `end_month` | `2024-03` | Khoảng tháng |
| `use_lset` | `true` | Bắt đầu từ LSET (tháng cuối của dãy tháng liên tục đã nạp thành công từ 2024-01) |
| `check_source_updates` | `true` (mặc định) | Chế độ `ALL`: với file đã SUCCESS, gửi `HEAD` lên TLC, so ETag/kích thước với `control.source_file_meta`; khác thì tải và nạp lại |
| `force_download` | `true` | Bỏ file Parquet local, tải lại từ TLC rồi mới nạp |

## Cách hoạt động

1. **Tải file**: nếu `data/raw/<file>` chưa có thì tải vào `<file>.tmp`, đủ mới đổi tên; thử lại 3 lần (chờ 3s, 6s). HTTP 403/404 (tháng nguồn chưa phát hành) dừng ngay, không thử lại.
2. **Nạp trong một transaction**: `DELETE` các dòng cũ của file đó, rồi `INSERT ... SELECT FROM read_parquet(...)`. Lỗi giữa chừng thì `ROLLBACK`, bảng giữ nguyên như trước. Vì vậy chạy lại một file không tạo dòng trùng.
3. **Khớp cột theo tên, không phân biệt hoa thường** (`VendorID` → `vendor_id`, `Airport_fee` → `airport_fee`).
   - **Kiểm tra schema drift:** file thiếu một cột bắt buộc thì lần nạp **FAILED**, log ghi danh sách cột hiện có, không nạp NULL âm thầm.
   - Chỉ `cbd_congestion_fee` được phép thiếu ở các file trước 2025-01 (khi đó nạp NULL).
   - Cột lạ trong file chỉ in `[SCHEMA WARN]`, không được nạp.
   - Đã kiểm tra: 24 file thật đều qua. File giả đổi tên `tip_amount` thì bị chặn.
4. **Phiên bản nguồn:** nạp thành công thì lưu ETag, Content-Length, Last-Modified của file trên TLC vào `control.source_file_meta`. Lượt `ALL` sau dùng các giá trị này để phát hiện TLC phát hành lại file.
5. **Cột kiểm toán**: `source_file_name`, `source_row_number` (thứ tự dòng trong file, từ 1), `batch_id`, `load_datetime`.
6. **Log**: mỗi file một dòng trong `control.etl_control` (`rows_read`, `rows_loaded`, `status`, `error_message`, thời gian).

`batch_id` có dạng `YYYYMMDDHHMMSS` và luôn lớn hơn `batch_id` lớn nhất đã ghi trong log. Fact incremental dựa vào điều này.

## Kiểm tra

```powershell
.\tasks.ps1 sql "select source_file_name, rows_read, rows_loaded, status, batch_id from control.etl_control order by control_id"
.\tasks.ps1 sql "select source_file_name, count(*) from raw.yellow_tripdata group by 1 order by 1"
```

Đối chiếu với file nguồn:

```powershell
.\tasks.ps1 sql "select regexp_extract(filename, '[^/]+$') f, count(*) from read_parquet('/home/src/data/raw/*.parquet', filename=true, union_by_name=true) group by 1 order by 1"
```

## Lưu ý

- **Một tiến trình ghi**: DuckDB khóa file khi ghi. Nếu file đang bị khóa (dbt, DBeaver, Power BI, một lượt Mage khác), block thử kết nối lại 5 lần (chờ 2, 4, 8, 16s) rồi báo lỗi. `.\tasks.ps1 sql` mở chế độ chỉ đọc nhưng vẫn không mở được khi có tiến trình đang ghi.
- **Dung lượng**: mỗi tháng khoảng 48–56 MB Parquet và ~3–3,5 triệu dòng. Đo ngày 16/11/2026: file DuckDB 336 MB sau 3 tháng (có 2 lần nạp lại), tức khoảng 100 MB/tháng; 24 tháng ước tính 2–3 GB. DuckDB không tự thu hồi chỗ của dòng đã xóa khi nạp lại; muốn thu gọn thì chép sang file mới (`ATTACH 'moi.duckdb' AS m; COPY FROM DATABASE nyc_taxi TO m;`).
- **Tên file** phải đúng dạng `yellow_tripdata_YYYY-MM.parquet`; tên khác bị từ chối.
- Nạp lại một tháng đã có trong Fact sẽ tạo `batch_id` mới, nên Fact incremental sẽ nạp lại tháng đó (trùng). Xử lý ở bước ELT.

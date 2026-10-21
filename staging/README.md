# Hướng dẫn cài môi trường và chạy phần Staging (Source → Staging)


> **Vì sao ai cũng phải tự nạp?** Git chỉ chứa code (script, pipeline), không chứa dữ liệu. Dữ liệu PostgreSQL nằm trong Docker volume trên máy của từng người, nên máy mới sẽ có database trống.

Người phụ trách phần này: Vân, nhánh `feat/staging-van`.

> File này đặt tại `staging/README.md`, là hướng dẫn riêng cho phần Staging. `README.md` ở thư mục gốc là của cả nhóm; chạy phần Staging thì xem file này.

---

## 1. Yêu cầu

- Docker Desktop (đang chạy), Git, PowerShell.
- Ổ đĩa còn trống: 24 file Parquet khoảng 1,5 GB; riêng bảng `stage.stg_yellow_taxi_trips` sau khi nạp đủ chiếm khoảng **20 GB** (đo thực tế bằng `pg_total_relation_size`). Nên chừa dư thêm cho Docker image và các bảng khác.
- Không cần cài Python hay PostgreSQL trên máy: mọi thứ chạy trong Docker.
- Cổng `5432` (PostgreSQL) và `6789` (Mage) phải trống.

## 2. Lấy code

```powershell
git clone https://github.com/nguyenanhtuan2702/NYC_TAXI.git
cd NYC_TAXI
git checkout feat/staging-van
```

(Khi nhánh đã được merge vào `develop` thì dùng `develop`.)

## 3. Tạo file `.env`

```powershell
Copy-Item .env.example .env
```

Mở `.env` bằng VS Code, đặt mật khẩu cho `POSTGRES_PASSWORD`. **Không commit file `.env`** (đã bị `.gitignore` chặn).

> Đặt mật khẩu **trước lần `docker compose up` đầu tiên**. Mật khẩu chỉ được gán cho database ở lần khởi tạo đầu; đổi `.env` sau đó thì database vẫn giữ mật khẩu cũ và Mage sẽ báo lỗi đăng nhập. Muốn đổi sau đó phải `docker compose down -v` (xóa toàn bộ dữ liệu).

## 4. Tải dữ liệu nguồn

```powershell
powershell -ExecutionPolicy Bypass -File data\download_raw.ps1
```

- Tải 24 file `yellow_tripdata_2024-01.parquet` … `yellow_tripdata_2025-12.parquet` vào `data\raw\`. File đã có thì bỏ qua.
- `data\raw\` bị `.gitignore` chặn nên không commit.
- Kiểm tra đủ 24 file:

```powershell
(Get-ChildItem data\raw\*.parquet).Count
```

Taxi Zone Lookup (`data\reference\taxi_zone_lookup.csv`) đã có sẵn trong repo.

## 5. Khởi động Docker

```powershell
docker compose up -d --build
docker compose ps
```

Kết quả mong đợi: container `nyc-postgres` ở trạng thái **healthy** và `nyc-mage` đang chạy. Lần đầu có thể mất vài phút để tải image.

Giao diện Mage: <http://localhost:6789>

Nếu Mage hiện trang đăng nhập: email `admin@admin.com`, mật khẩu `admin` (tài khoản mặc định của Mage, chỉ chạy trên máy mình).

## 6. Kiểm tra bảng Staging đã được tạo

Khi database được tạo lần đầu, Docker tự chạy các file trong `staging/init_sql/` (`01_init_schemas.sql`, `02_create_stage.sql`).

```powershell
docker compose exec postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "\dt stage.*" -c "\dt control.*"
```

Phải thấy: `stage.stg_yellow_taxi_trips`, `stage.stg_taxi_zone_lookup`, `control.etl_control`.

Nếu thiếu bảng, chạy tay:

```powershell
docker compose exec postgres psql -U taxi_user -d nyc_taxi_staging -f /docker-entrypoint-initdb.d/01_init_schemas.sql
docker compose exec postgres psql -U taxi_user -d nyc_taxi_staging -f /docker-entrypoint-initdb.d/02_create_stage.sql
```

## 7. Nạp dữ liệu bằng Mage

Hai pipeline có sẵn trong repo, **không cần tạo block hay dán code**: sau khi pull code, Mage tự hiện chúng trong danh sách Pipelines.

### 7.1. Taxi Zone Lookup (265 dòng)

1. Vào <http://localhost:6789> → **Pipelines** → mở `letter_01_ingest_source_to_postgres`.
2. Ở block `export_zone_lookup`, bấm `⋮` → **Execute with all upstream blocks**.
3. Đợi cả hai block có dấu tích xanh.

(Tên có tiền tố `letter_` vì Mage không cho tên bắt đầu bằng số.)

### 7.2. Chuyến đi Yellow Taxi (Parquet)

Mở pipeline `ingest_trips_to_postgres`. Biến `file_name` quyết định nạp gì:

| Giá trị `file_name` | Ý nghĩa |
|---|---|
| `yellow_tripdata_2024-01.parquet` | Chỉ nạp file đó |
| `ALL` (mặc định nếu không đặt) | Nạp mọi file trong `data\raw`, bỏ qua file đã có log SUCCESS |

**Nên thử một tháng trước** (khoảng vài phút):

1. Trong pipeline, mở thanh bên phải, chọn biểu tượng **Variables** (`x=`) → **New**.
2. Tên `file_name`, giá trị `yellow_tripdata_2024-01.parquet`. **Bấm Enter để lưu** (không lưu thì block dùng giá trị mặc định).
3. Bấm ▶ ở block `load_trips_to_stage` và đợi dấu tích xanh. Cuối log in một dòng dạng:
   `yellow_tripdata_2024-01.parquet SUCCESS 2964624 2964624 None`

**Nạp toàn bộ 24 tháng:**

1. Đổi giá trị `file_name` thành `ALL`, bấm Enter.
2. Bấm ▶ **một lần** ở block `load_trips_to_stage`. Mất khá lâu (tùy máy), nên cắm sạc và giữ tab Mage mở.
3. **Đừng bấm chạy lần hai khi block còn đang chạy.**
4. Nếu dừng giữa chừng vì lỗi: sửa nguyên nhân rồi bấm ▶ lại; các tháng đã xong sẽ được bỏ qua.

Theo dõi tiến độ:

```powershell
docker compose exec postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT source_file_name, rows_read, rows_loaded, status FROM control.etl_control ORDER BY control_id;"
```

## 8. Kiểm tra kết quả

Sau khi nạp đủ, kết quả đúng là:

| Kiểm tra | Kết quả mong đợi |
|---|---|
| Tổng dòng `stg_yellow_taxi_trips` | **89.892.322** dòng, **24** file |
| `stg_taxi_zone_lookup` | **265** dòng |
| Tháng thiếu | 0 tháng |
| File có `rows_read <> rows_loaded` hoặc status khác SUCCESS | 0 file |

```powershell
docker compose exec postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT count(*) AS tong_dong, count(DISTINCT source_file_name) AS so_file FROM stage.stg_yellow_taxi_trips;"
```

(Lệnh đếm quét toàn bảng nên mất vài phút.) Cách nhanh hơn là cộng từ log:

```powershell
docker compose exec postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT count(*) AS so_file, sum(rows_loaded) AS tong_dong FROM (SELECT DISTINCT ON (source_file_name) source_file_name, rows_loaded FROM control.etl_control WHERE status='SUCCESS' ORDER BY source_file_name, control_id DESC) t;"
```

Tìm tháng chưa nạp:

```powershell
docker compose exec postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT to_char(m,'YYYY-MM') AS thang_thieu FROM generate_series('2024-01-01'::date,'2025-12-01','1 month') m WHERE NOT EXISTS (SELECT 1 FROM control.etl_control c WHERE c.status='SUCCESS' AND c.source_file_name='yellow_tripdata_'||to_char(m,'YYYY-MM')||'.parquet');"
```

Phải trả về `(0 rows)`.

## 9. Chạy lại

- **Nạp lại một tháng:** đặt `file_name` là tên file đó rồi bấm ▶. Block xóa các dòng cũ của đúng file đó trước khi nạp, nên số dòng không bị nhân đôi. `control.etl_control` thêm một dòng log mới (log cũ được giữ làm lịch sử).
- **Chạy lại Zone Lookup:** pipeline tự `TRUNCATE` rồi nạp lại, kết quả vẫn 265 dòng.
- **Làm lại từ đầu (xóa sạch dữ liệu):** `docker compose down -v` rồi `docker compose up -d --build`. Lệnh `-v` xóa toàn bộ volume PostgreSQL, nên chỉ dùng khi thật sự muốn nạp lại từ đầu.

Hằng ngày: `docker compose up -d` để bật, `docker compose down` để tắt (**không** thêm `-v`).

## 10. Các truy vấn đo lỗi dữ liệu thô

Nằm trong `staging/pg_checks/`. Mỗi file quét toàn bảng nên mất vài phút: **chạy từng file, đợi xong mới chạy file tiếp theo**.

| File | Khảo sát |
|---|---|
| `02_profile_errors.sql` | Số dòng của từng loại lỗi trên toàn bảng |
| `03_profile_by_vendor.sql` | Lỗi theo nhà cung cấp |
| `04_profile_negative_fare.sql` | Giá âm theo loại thanh toán |
| `05_profile_nulls.sql` | Số dòng NULL của từng cột, khoảng thời gian đón/trả |
| `06_profile_categorical.sql` | Các giá trị của cột phân loại |
| `07_profile_outliers.sql` | Giá trị cực đoan, phụ phí âm |
| `08_profile_by_month.sql` | Lỗi theo từng tháng |
| `09_profile_followup.sql` | Dòng đón khách ngoài kỳ theo file, đột biến ở tháng 11 |

Lệnh chạy một file (thay `<tên file>`):

```powershell
Get-Content staging\pg_checks\<tên file> | docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging
```

Với `02`, `05`, `07` thêm `-x` sau `-P pager=off` để kết quả in theo dạng dọc (mỗi chỉ số một dòng).

Kết quả được phân tích trong báo cáo phần Staging. **Stage giữ dữ liệu thô, không lọc**; các bản ghi lỗi chưa được xử lý ở tầng này.

## 11. Thông tin cho người dùng bảng Stage

- Tên bảng: `stage.stg_yellow_taxi_trips`, `stage.stg_taxi_zone_lookup`. Cột chữ thường, snake_case (`vendor_id`, `ratecode_id`, `pu_location_id`, `do_location_id`, `airport_fee`, ...).
- Bốn cột audit ở bảng chuyến đi: `source_file_name`, `source_row_number`, `batch_id`, `load_datetime`.
- `cbd_congestion_fee` là NULL với toàn bộ 12 tháng 2024.
- Giờ đón/trả khách giữ nguyên giờ địa phương New York như nguồn. `batch_id` và `load_datetime` theo giờ của container (UTC).
- Khóa liên kết địa lý là `location_id` (không join theo tên Zone vì có tên trùng).
- Nối với Zone Lookup: `pu_location_id`/`do_location_id` không có NULL và đều nằm trong 1–265.
- Cột có NULL: `passenger_count`, `ratecode_id`, `store_and_fwd_flag`, `congestion_surcharge`, `airport_fee` (mỗi cột 15.703.126 dòng) và `cbd_congestion_fee` (41.169.720 dòng). Các cột còn lại không có NULL.
- Các cột tiền và quãng đường giữ kiểu `double precision` đúng như nguồn (Stage là bản sao 1:1, không làm tròn). Nếu cần `DECIMAL`, ép kiểu ở tầng DDS trước khi cộng dồn.

## 12. Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| `port is already allocated` khi `docker compose up` | Có container khác đang dùng cổng 5432/6789 (ví dụ container lab của thầy). Dừng nó: `docker stop lab-mage lab-postgres` |
| Mage không kết nối được PostgreSQL | `docker compose ps` xem `nyc-postgres` đã healthy chưa; kiểm tra `.env`. Trong container, host là `postgres`, không phải `localhost` |
| Block báo không tìm thấy file | Tên `file_name` sai hoặc thừa dấu cách; hoặc chưa tải dữ liệu. Kiểm tra: `docker compose exec mage ls /home/src/data/raw` |
| Chạy ra tháng 2024-01 dù đặt tháng khác | Biến `file_name` chưa được lưu. Bấm Enter trong ô giá trị rồi chạy lại (không làm hỏng dữ liệu) |
| Output của `psql` bị cuộn trang hoặc lộn dòng | Luôn thêm `-P pager=off`; chữ rác trong terminal chỉ là lỗi hiển thị |
| Dán nhiều dòng vào PowerShell bị rớt dòng | Tạo file bằng VS Code (dán, Ctrl+S), chỉ dán lệnh ngắn vào terminal |
| VS Code cảnh báo `Import "mage_ai..." could not be resolved` | Vô hại: thư viện `mage_ai` chỉ có trong container, code vẫn chạy bình thường |
| Hết dung lượng ổ đĩa khi nạp | Giải phóng ổ rồi chạy lại với `file_name = ALL`; các tháng đã xong được bỏ qua |
| `git status` thấy `mage_data/`, `mage/.ssh_tunnel/`, `mage/.file_versions/` | Không commit; các thư mục này do Mage tự sinh |

## 13. Cấu trúc liên quan

```text
data/
  raw/                 24 file Parquet (không commit)
  reference/           taxi_zone_lookup.csv, taxi_zones.zip
  download_raw.ps1     script tải dữ liệu
staging/
  README.md            file này
  init_sql/            01_init_schemas.sql, 02_create_stage.sql
  pg_checks/           inspect_parquet.py (đọc schema Parquet), 02–09 truy vấn đo lỗi dữ liệu thô
mage/
  data_loaders/        load_zone_lookup.py
  data_exporters/      export_zone_lookup.py, load_trips_to_stage.py
  pipelines/           letter_01_ingest_source_to_postgres, ingest_trips_to_postgres
  io_config.yaml       đọc thông tin kết nối từ biến môi trường (.env)
```

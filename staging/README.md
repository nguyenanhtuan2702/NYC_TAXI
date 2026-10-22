# Hướng dẫn cài môi trường và chạy phần Staging (Source → Staging)


> **Vì sao ai cũng phải tự nạp?** Git chỉ chứa code (script, pipeline), không chứa dữ liệu. Dữ liệu PostgreSQL nằm trong Docker volume trên máy của từng người, nên máy mới sẽ có database trống.

Người phụ trách phần này: Vân, nhánh `feat/staging-van`.

> File này đặt tại `staging/README.md`, là hướng dẫn riêng cho phần Staging. `README.md` ở thư mục gốc là của cả nhóm; chạy phần Staging thì xem file này.

---

## 1. Yêu cầu

- Docker Desktop (đang chạy), Git, PowerShell.
- Ổ đĩa còn trống: 24 file Parquet khoảng 1,5 GB; riêng bảng `stage.stg_yellow_taxi_trips` sau khi nạp đủ chiếm khoảng **20 GB** (đo thực tế bằng `pg_total_relation_size`). Nên chừa dư thêm cho Docker image và các bảng khác.
- RAM: nên có từ **12 GB**. `docker-compose.yml` giới hạn PostgreSQL 3,5 GB và Mage 2,5 GB. Trên Windows nên tạo file `%USERPROFILE%\.wslconfig` để WSL không chiếm hết RAM máy:

  ```ini
  [wsl2]
  memory=7GB
  processors=4
  swap=4GB
  ```

  Máy 8 GB thì đặt `memory=5GB`. Sau khi tạo, chạy `wsl --shutdown` rồi mở lại Docker Desktop.
- Không cần cài Python hay PostgreSQL trên máy: mọi thứ chạy trong Docker.
- Cổng `5432` (PostgreSQL) và `6789` (Mage) phải trống.
- Cần có Internet khi nạp lần đầu (pipeline tự tải file Parquet từ CloudFront).

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

## 4. Dữ liệu nguồn (tự động tải)

Pipeline `ingest_trips_to_postgres` **tự tải** các file Parquet còn thiếu từ CloudFront vào `data\raw\`, nên **không cần chạy script tải trước**.

- File được tải vào file tạm `.tmp`, chỉ đổi tên thành `.parquet` khi tải đủ 100%. Lỗi mạng thì tự thử lại tối đa 3 lần (chờ 3s, 6s, 12s).
- File đã có trong `data\raw\` thì không tải lại.
- `data\raw\` bị `.gitignore` chặn nên không commit.
- Nếu muốn tải trước, vẫn dùng được script cũ:

  ```powershell
  powershell -ExecutionPolicy Bypass -File data\download_raw.ps1
  ```

- Kiểm tra đủ 24 file (`yellow_tripdata_2024-01.parquet` … `yellow_tripdata_2025-12.parquet`):

  ```powershell
  (Get-ChildItem data\raw\*.parquet).Count
  ```

Phạm vi nạp cố định là 24 tháng 2024–2025. Taxi Zone Lookup (`data\reference\taxi_zone_lookup.csv`) đã có sẵn trong repo.

## 5. Khởi động Docker

```powershell
docker compose up -d --build
docker compose ps
```

Kết quả mong đợi: container `nyc-postgres` ở trạng thái **healthy** và `nyc-mage` đang chạy. Lần đầu có thể mất vài phút để tải image.

Cấu hình Docker đã tối ưu cho nạp dữ liệu lớn:

- Hai container có `restart: unless-stopped` (tự lên lại khi máy khởi động; container do mình tự `docker stop` thì phải `docker start`).
- Giới hạn RAM: PostgreSQL 3,5 GB, Mage 2,5 GB.
- PostgreSQL chạy với `synchronous_commit=off`, `max_wal_size=4GB`, `checkpoint_timeout=15min` để nạp hàng chục triệu dòng không bị nghẽn ổ đĩa.

Giao diện Mage: <http://localhost:6789>

Nếu Mage hiện trang đăng nhập: email `admin@admin.com`, mật khẩu `admin` (tài khoản mặc định của Mage, chỉ chạy trên máy mình).

## 6. Kiểm tra bảng Staging đã được tạo

Khi database được tạo lần đầu, Docker tự chạy các file trong `staging/init_sql/` (`01_init_schemas.sql`, `02_create_stage.sql`).

```powershell
docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "\dt stage.*" -c "\dt control.*"
```

Phải thấy: `stage.stg_yellow_taxi_trips`, `stage.stg_taxi_zone_lookup`, `control.etl_control`.

Nếu thiếu bảng, chạy tay:

```powershell
docker compose exec -T postgres psql -U taxi_user -d nyc_taxi_staging -f /docker-entrypoint-initdb.d/01_init_schemas.sql
docker compose exec -T postgres psql -U taxi_user -d nyc_taxi_staging -f /docker-entrypoint-initdb.d/02_create_stage.sql
```

> Các lệnh `docker compose exec` trong tài liệu này đều có `-T`. Thiếu `-T`, terminal PowerShell có thể làm mất ô giá trị của kết quả (chỉ còn tiêu đề và `(1 row)`).

## 7. Nạp dữ liệu bằng Mage

Hai pipeline có sẵn trong repo, **không cần tạo block hay dán code**: sau khi pull code, Mage tự hiện chúng trong danh sách Pipelines.

### 7.1. Taxi Zone Lookup (265 dòng)

1. Vào <http://localhost:6789> → **Pipelines** → mở `letter_01_ingest_source_to_postgres`.
2. Ở block `export_zone_lookup`, bấm `⋮` → **Execute with all upstream blocks**.
3. Đợi cả hai block có dấu tích xanh.

(Tên có tiền tố `letter_` vì Mage không cho tên bắt đầu bằng số.)

### 7.2. Chuyến đi Yellow Taxi (Parquet)

Mở pipeline `ingest_trips_to_postgres`. Các biến (Variables) quyết định nạp gì:

| Biến | Ý nghĩa |
|---|---|
| `file_name` | Một file cụ thể (ví dụ `yellow_tripdata_2024-01.parquet`), hoặc `ALL` (mặc định) |
| `year` | Chỉ nạp năm đó, ví dụ `2024` |
| `start_month` / `end_month` | Khoảng tháng, ví dụ `2024-01` đến `2024-03` |
| `use_lset` | `true`: bắt đầu từ tháng LSET (tháng cuối của dãy tháng liên tục đã nạp thành công) |

Quy tắc chạy:

- Khi `file_name` là `ALL` (hoặc không đặt), pipeline duyệt các tháng theo bộ lọc `year`, `start_month`, `end_month`, `use_lset`; không đặt bộ lọc nào thì duyệt cả 24 tháng.
- Tháng đã có log `SUCCESS` luôn bị bỏ qua.
- Mỗi file lỗi được ghi log `FAILED` riêng, pipeline vẫn nạp tiếp các tháng sau. Cuối lần chạy in dòng `=== TỔNG KẾT` và **báo đỏ nếu còn file lỗi**. Bấm ▶ lại thì chỉ nạp các file lỗi.
- **LSET** (Last Successful Extraction Time) là tháng dữ liệu cuối cùng của dãy tháng liên tục, tính từ 2024-01, đã nạp thành công. **CET** (Current Extraction Time) là thời điểm bắt đầu lần chạy hiện tại, được ghi vào `last_extract_time` của `control.etl_control`.
- Tháng chưa được nguồn phát hành (HTTP 403/404) cũng được ghi log `FAILED`.

**Nên thử một tháng trước** (khoảng vài phút):

1. Trong pipeline, mở thanh bên phải, chọn biểu tượng **Variables** (`x=`) → **New**.
2. Tên `file_name`, giá trị `yellow_tripdata_2024-01.parquet`. **Bấm Enter để lưu** (không lưu thì block dùng giá trị mặc định).
3. Bấm ▶ ở block `load_trips_to_stage` và đợi dấu tích xanh. Cuối log in một dòng dạng:
   `[SUCCESS] yellow_tripdata_2024-01.parquet | đọc 2,964,624 | nạp 2,964,624 | None`

**Nạp toàn bộ 24 tháng:**

1. Đặt `file_name` là `ALL` (xóa các biến `year`, `start_month`, `end_month`, `use_lset` nếu còn), bấm Enter.
2. Bấm ▶ **một lần** ở block `load_trips_to_stage`. Mất khá lâu (tùy mạng và máy, vì phải tải khoảng 1,5 GB rồi nạp ~90 triệu dòng), nên cắm sạc và giữ tab Mage mở.
3. **Đừng bấm chạy lần hai khi block còn đang chạy.**
4. Nếu dừng giữa chừng vì lỗi: sửa nguyên nhân rồi bấm ▶ lại; các tháng đã xong sẽ được bỏ qua.

> Khi đổi biến trên giao diện, Mage ghi giá trị vào `mage/pipelines/ingest_trips_to_postgres/metadata.yaml`. **Đừng commit thay đổi này**; trước khi commit hãy khôi phục: `git checkout -- mage/pipelines/ingest_trips_to_postgres/metadata.yaml`.

Theo dõi tiến độ:

```powershell
docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT source_file_name, rows_read, rows_loaded, status, finished_at FROM control.etl_control ORDER BY control_id;"
```

## 8. Kiểm tra kết quả

Sau khi nạp đủ, kết quả đúng là:

| Kiểm tra | Kết quả mong đợi |
|---|---|
| Tổng dòng `stg_yellow_taxi_trips` | **89.892.322** dòng, **24** file |
| `stg_taxi_zone_lookup` | **265** dòng |
| Tháng thiếu | 0 tháng |
| File có `rows_read <> rows_loaded` hoặc status khác SUCCESS | 0 file |
| Dòng log thiếu `last_extract_time` hoặc `finished_at` (log của các lần chạy mới) | 0 dòng |

```powershell
docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT count(*) AS tong_dong, count(DISTINCT source_file_name) AS so_file FROM stage.stg_yellow_taxi_trips;"
```

(Lệnh đếm quét toàn bảng nên mất vài phút.) Cách nhanh hơn là cộng từ log:

```powershell
docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT count(*) AS so_file, sum(rows_loaded) AS tong_dong FROM (SELECT DISTINCT ON (source_file_name) source_file_name, rows_loaded FROM control.etl_control WHERE status='SUCCESS' ORDER BY source_file_name, control_id DESC) t;"
```

Tìm tháng chưa nạp:

```powershell
docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT to_char(m,'YYYY-MM') AS thang_thieu FROM generate_series('2024-01-01'::date,'2025-12-01','1 month') m WHERE NOT EXISTS (SELECT 1 FROM control.etl_control c WHERE c.status='SUCCESS' AND c.source_file_name='yellow_tripdata_'||to_char(m,'YYYY-MM')||'.parquet');"
```

Phải trả về `(0 rows)`.

Thời gian nạp mỗi tháng và tổng thời gian (giờ trong log là UTC):

```powershell
docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT source_file_name, finished_at - started_at AS thoi_gian FROM control.etl_control WHERE status='SUCCESS' AND finished_at IS NOT NULL ORDER BY control_id;"
```

## 9. Chạy lại và tự hồi phục

- **Nạp lại một tháng:** đặt `file_name` là tên file đó rồi bấm ▶. Nếu file từng được nạp (đã có log), block xóa các dòng cũ của đúng file đó trước khi nạp, nên số dòng không bị nhân đôi. `control.etl_control` thêm một dòng log mới (log cũ được giữ làm lịch sử).
- **Mất kết nối PostgreSQL giữa chừng:** code tự thử kết nối lại (chờ 2s, 4s, 8s, 16s, tối đa 5 lần), dữ liệu dở dang của file được `ROLLBACK`, và log `FAILED` được ghi bằng một kết nối mới. Chỉ cần đợi `nyc-postgres` healthy rồi bấm ▶ lại.
- **File Parquet thiếu hoặc tải lỗi:** pipeline tự tải lại; nếu thất bại sau 3 lần thì ghi log `FAILED` cho file đó và nạp tiếp các tháng sau.
- **Chạy lại Zone Lookup:** pipeline tự `TRUNCATE` rồi nạp lại, kết quả vẫn 265 dòng.
- **Làm lại từ đầu (xóa sạch dữ liệu):** `docker compose down -v` rồi `docker compose up -d --build`, sau đó nạp lại Zone Lookup (mục 7.1) và chuyến đi (mục 7.2). Lệnh `-v` xóa toàn bộ volume PostgreSQL, nên chỉ dùng khi thật sự muốn nạp lại từ đầu.

Hằng ngày: `docker compose up -d` để bật, `docker compose down` để tắt (**không** thêm `-v`).

## 10. Các truy vấn đo lỗi dữ liệu thô

Nằm trong `staging/pg_checks/`. Các file `02`–`09` và `11` quét toàn bảng nên mất vài phút: **chạy từng file, đợi xong mới chạy file tiếp theo**. File `10` chỉ quét một file nguồn nên nhanh hơn.

| File | Khảo sát |
|---|---|
| `02_profile_errors.sql` | Số dòng của từng loại lỗi trên toàn bảng; kèm truy vấn kiểm chứng 5 cột NULL có trùng đúng tập `payment_type = 0` (Flex Fare) hay không |
| `03_profile_by_vendor.sql` | Lỗi theo nhà cung cấp |
| `04_profile_negative_fare.sql` | Đối chiếu `fare_amount` âm và `total_amount` âm theo loại thanh toán |
| `05_profile_nulls.sql` | Số dòng NULL của từng cột, khoảng thời gian đón/trả |
| `06_profile_categorical.sql` | Các giá trị của cột phân loại |
| `07_profile_outliers.sql` | Giá trị cực đoan (quãng đường, tiền, vận tốc > 100 mph), các khoản phụ phí âm |
| `08_profile_by_month.sql` | Lỗi theo từng file nguồn (từng tháng) |
| `09_profile_followup.sql` | Các file có dòng đón ngoài kỳ 2024–2025; top 5 giờ có nhiều chuyến "trả trước đón" ở tháng 11/2024 và 11/2025 |
| `10_profile_duplicates.sql` | Các nhóm dòng trùng hoàn toàn trong **một file nguồn** (cần truyền tên file, xem bên dưới) |
| `11_profile_consistency.sql` | Tổng tiền không khớp tổng các khoản thành phần theo loại thanh toán; thống kê Zone Lookup (số dòng, mã nhỏ nhất/lớn nhất); tên Zone bị trùng ở nhiều mã |

Lệnh chạy một file (thay `<tên file>`):

```powershell
Get-Content staging\pg_checks\<tên file> | docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging
```

Với `02`, `05`, `07` thêm `-x` sau `-P pager=off` để kết quả in theo dạng dọc (mỗi chỉ số một dòng).

File `10` cần truyền tên file nguồn bằng `-v f=...` (thay tên file muốn kiểm tra):

```powershell
Get-Content staging\pg_checks\10_profile_duplicates.sql | docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -v f=yellow_tripdata_2024-01.parquet
```

Kết quả được phân tích trong báo cáo phần Staging. **Stage giữ dữ liệu thô, không lọc**; các bản ghi lỗi chưa được xử lý ở tầng này.

## 11. Thông tin cho người dùng bảng Stage

- Tên bảng: `stage.stg_yellow_taxi_trips`, `stage.stg_taxi_zone_lookup`. Cột chữ thường, snake_case (`vendor_id`, `ratecode_id`, `pu_location_id`, `do_location_id`, `airport_fee`, ...).
- Bốn cột audit ở bảng chuyến đi: `source_file_name`, `source_row_number`, `batch_id`, `load_datetime`.
- `cbd_congestion_fee` là NULL với toàn bộ 12 tháng 2024.
- Giờ đón/trả khách giữ nguyên giờ địa phương New York như nguồn. `batch_id`, `load_datetime` và các mốc thời gian trong `control.etl_control` (`started_at`, `finished_at`, `last_extract_time`) theo giờ của container (UTC).
- Khóa liên kết địa lý là `location_id` (không join theo tên Zone vì có tên trùng).
- Nối với Zone Lookup: `pu_location_id`/`do_location_id` không có NULL và đều nằm trong 1–265.
- Cột có NULL: `passenger_count`, `ratecode_id`, `store_and_fwd_flag`, `congestion_surcharge`, `airport_fee` (mỗi cột 15.703.126 dòng) và `cbd_congestion_fee` (41.169.720 dòng). Các cột còn lại không có NULL.
- Các cột tiền và quãng đường giữ kiểu `double precision` đúng như nguồn (Stage là bản sao 1:1, không làm tròn). Nếu cần `DECIMAL`, ép kiểu ở tầng DDS trước khi cộng dồn.

## 12. Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| `port is already allocated` khi `docker compose up` | Có container khác đang dùng cổng 5432/6789 (ví dụ container lab của thầy). Dừng nó: `docker stop lab-mage lab-postgres` |
| Mage không kết nối được PostgreSQL | `docker compose ps` xem `nyc-postgres` đã healthy chưa; kiểm tra `.env`. Trong container, host là `postgres`, không phải `localhost` |
| Block báo không tìm thấy file hoặc tải lỗi | Kiểm tra mạng và tên `file_name` (không thừa dấu cách). Xem file đã về chưa: `docker compose exec -T mage ls /home/src/data/raw`. Bấm ▶ lại để tải lại |
| Chạy ra tháng 2024-01 dù đặt tháng khác | Biến `file_name` chưa được lưu. Bấm Enter trong ô giá trị rồi chạy lại (không làm hỏng dữ liệu) |
| Kết quả `psql` mất ô giá trị, chỉ thấy tiêu đề và `(1 row)` | Thêm `-T` sau `exec`: `docker compose exec -T postgres psql ...` (hoặc ghi ra file rồi `Get-Content`) |
| Output của `psql` bị cuộn trang hoặc lộn dòng | Luôn thêm `-P pager=off`; chữ rác trong terminal chỉ là lỗi hiển thị |
| `git diff` dừng ở dấu `:` | Bấm `q` để thoát, hoặc dùng `git --no-pager diff` |
| Dán nhiều dòng vào PowerShell bị rớt dòng | Tạo file bằng VS Code (dán, Ctrl+S), chỉ dán lệnh ngắn vào terminal |
| VS Code cảnh báo `Import "mage_ai..." could not be resolved` | Vô hại: thư viện `mage_ai` chỉ có trong container, code vẫn chạy bình thường |
| Docker đứng hình, `vmmemWSL` ăn hết RAM | Đặt `memory=` trong `.wslconfig`, chạy `wsl --shutdown`, mở lại Docker Desktop; nạp từng năm (`year` = `2024` rồi `2025`) |
| Chạy `10_profile_duplicates.sql` báo `syntax error at or near ":"` | Chưa truyền tên file. Thêm `-v f=<tên file>.parquet` vào lệnh `psql`, ví dụ `-v f=yellow_tripdata_2024-01.parquet` |
| Hết dung lượng ổ đĩa khi nạp | Giải phóng ổ rồi chạy lại với `file_name = ALL`; các tháng đã xong được bỏ qua |
| `git status` thấy `mage_data/`, `mage/.ssh_tunnel/`, `mage/.file_versions/` | Không commit; các thư mục này do Mage tự sinh |
| `git status` thấy `metadata.yaml` của pipeline bị sửa | Do đổi biến trên giao diện Mage. Khôi phục: `git checkout -- mage/pipelines/ingest_trips_to_postgres/metadata.yaml` |

## 13. Cấu trúc liên quan

```text
data/
  raw/                 24 file Parquet (không commit, pipeline tự tải)
  reference/           taxi_zone_lookup.csv, taxi_zones.zip
  download_raw.ps1     script tải dữ liệu (tùy chọn)
staging/
  README.md            file này
  init_sql/            01_init_schemas.sql, 02_create_stage.sql
    pg_checks/           inspect_parquet.py (đọc schema Parquet), 02–11 truy vấn đo lỗi dữ liệu thô
mage/
  data_loaders/        load_zone_lookup.py
  data_exporters/      export_zone_lookup.py, load_trips_to_stage.py
  pipelines/           letter_01_ingest_source_to_postgres, ingest_trips_to_postgres
  io_config.yaml       đọc thông tin kết nối từ biến môi trường (.env)
docker-compose.yml     PostgreSQL + Mage, có giới hạn RAM và restart tự động
```

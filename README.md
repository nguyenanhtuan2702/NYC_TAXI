# NYC Yellow Taxi Data Warehouse

Dự án xây dựng quy trình xử lý và phân tích dữ liệu **NYC Yellow Taxi Trip Records** cho giai đoạn 2024–2025. Phạm vi hiện thực trong repo tập trung vào nạp dữ liệu nguồn vào PostgreSQL Staging bằng Mage.ai. Các thư mục dbt, warehouse, Power BI và pipeline ELT tổng thể hiện mới là khung để phát triển tiếp.

## Trạng thái dự án

| Hạng mục | Trạng thái hiện tại |
|---|---|
| PostgreSQL Staging | Có DDL tạo schema, bảng chuyến đi, bảng Zone Lookup và bảng log ETL |
| Nạp dữ liệu bằng Mage.ai | Có pipeline nạp Taxi Zone Lookup và Yellow Taxi Parquet; pipeline chuyến đi hỗ trợ tải file, retry, nạp theo batch và chạy lại |
| Docker Compose | Có cấu hình chạy PostgreSQL và Mage.ai |
| dbt / DDS / OLAP | Có cấu trúc thư mục, chưa có `dbt_project.yml`, model, package hoặc cấu hình để chạy dbt |
| End-to-end ELT | Chưa có pipeline triển khai trong `mage/pipelines/02_end_to_end_elt_pipeline/` |
| Power BI | Có thư mục khung; chưa có báo cáo `.pbip` hoặc dashboard hoàn chỉnh |

> README này mô tả trạng thái của repo hiện tại. Các mô hình Dimension, Fact, truy vấn OLAP và dashboard là mục tiêu phát triển tiếp, không phải chức năng đã triển khai đầy đủ.

## Kiến trúc

```text
NYC Taxi source files
        │
        ▼
Mage.ai ingestion
        │
        ▼
PostgreSQL: stage / control
        │
        ├── stage.stg_yellow_taxi_trips
        ├── stage.stg_taxi_zone_lookup
        └── control.etl_control
        │
        ▼
dbt DDS / OLAP / Power BI (kế hoạch phát triển)
```

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Dữ liệu chuyến đi | Parquet | Yellow Taxi Trip Records theo tháng, 2024–2025 |
| Dữ liệu tham chiếu | CSV, ZIP | Taxi Zone Lookup và ranh giới Taxi Zone |
| Orchestration / ingestion | Mage.ai, Python, PyArrow | Đọc, tải và nạp dữ liệu vào PostgreSQL |
| Staging / control | PostgreSQL | Lưu dữ liệu nguồn và lịch sử các lần nạp |
| Transformation / analytics | dbt, PostgreSQL | Dự kiến xây dựng DDS, Dimension, Fact và các mart OLAP |
| Visualization | Power BI | Dự kiến xây dựng dashboard và bản đồ |

## Cấu trúc repository

```text
NYC_TAXI/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── README.md
├── data/
│   ├── download_raw.ps1
│   ├── raw/                         # File tải về, không commit
│   ├── reference/                   # Taxi Zone Lookup và ranh giới khu vực
│   └── sample/                      # Dữ liệu mẫu (nếu có)
├── dbt/                             # Khung thư mục; chưa có cấu hình dự án dbt
│   ├── macros/
│   ├── models/
│   │   ├── staging/
│   │   ├── dds/
│   │   └── olap_marts/
│   ├── seeds/
│   └── tests/
├── docs/
│   ├── 01_data_modeling/
│   ├── 02_test_plans_and_logs/
│   └── 03_reports/
├── mage/
│   ├── data_exporters/
│   ├── data_loaders/
│   ├── pipelines/
│   ├── transformers/
│   ├── custom/
│   └── io_config.yaml
├── mage_data/                       # Dữ liệu Mage sinh ra khi chạy
├── powerbi/
│   ├── dax/
│   └── map_shapes/
├── staging/
│   ├── README.md                    # Hướng dẫn chi tiết chạy Staging
│   ├── init_sql/                    # DDL khởi tạo schema và bảng
│   └── pg_checks/                   # SQL/Python kiểm tra dữ liệu nguồn
└── warehouse/                       # Vị trí dành cho đầu ra warehouse cục bộ
```

Các file hướng dẫn chi tiết:

- [Hướng dẫn chạy Staging](staging/README.md)

## Yêu cầu

- Git
- Docker Desktop và Docker Compose
- PowerShell trên Windows (các lệnh trong hướng dẫn chạy Staging sử dụng PowerShell)
- Kết nối Internet khi cần tải Parquet từ nguồn
- Đủ dung lượng cho dữ liệu và Docker. Theo hướng dẫn Staging, toàn bộ dữ liệu Parquet khoảng 1,5 GB và bảng staging có thể chiếm khoảng 20 GB sau khi nạp đủ.
- Nên có RAM từ 12 GB để chạy cấu hình Docker hiện tại; tham khảo cách giới hạn WSL trong [staging/README.md](staging/README.md).

Không cần cài PostgreSQL hoặc Python trực tiếp trên máy để chạy các pipeline Mage trong Docker.

## Bắt đầu nhanh: PostgreSQL Staging và Mage

### 1. Lấy source và cấu hình môi trường

```powershell
git clone https://github.com/nguyenanhtuan2702/NYC_TAXI.git
Set-Location NYC_TAXI
Copy-Item .env.example .env
```

Mở `.env`, thay `POSTGRES_PASSWORD=change_me` bằng mật khẩu riêng trước lần khởi động đầu tiên. Không commit `.env`.

Các biến mặc định trong `.env.example`:

| Biến | Giá trị mẫu | Ý nghĩa |
|---|---|---|
| `POSTGRES_DB` | `nyc_taxi_staging` | Tên database |
| `POSTGRES_USER` | `taxi_user` | Tài khoản database |
| `POSTGRES_PASSWORD` | `change_me` | Cần thay bằng mật khẩu riêng |
| `POSTGRES_HOST` | `postgres` | Tên service trong Docker network |
| `POSTGRES_PORT` | `5432` | Cổng PostgreSQL trong Docker network |

### 2. Khởi động dịch vụ

```powershell
docker compose up -d --build
docker compose ps
```

Chờ service `postgres` ở trạng thái `healthy` và Mage chạy. Giao diện Mage: <http://localhost:6789>.

Docker Compose cấu hình PostgreSQL và Mage với `restart: unless-stopped`, giới hạn bộ nhớ, và healthcheck cho PostgreSQL. Các tham số cụ thể nằm trong [docker-compose.yml](docker-compose.yml).

### 3. Xác nhận các bảng Staging

Các script trong `staging/init_sql/` được PostgreSQL image chạy khi khởi tạo volume lần đầu. Kiểm tra bảng:

```powershell
docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "\dt stage.*" -c "\dt control.*"
```

Các bảng dự kiến:

- `stage.stg_yellow_taxi_trips`
- `stage.stg_taxi_zone_lookup`
- `control.etl_control`

Nếu đã có volume PostgreSQL từ trước, thay đổi các script khởi tạo không tự chạy lại trên volume đó. Hướng dẫn kiểm tra và chạy DDL thủ công xem trong [staging/README.md](staging/README.md).

### 4. Nạp Taxi Zone Lookup

Trong Mage, mở pipeline `letter_01_ingest_source_to_postgres`, sau đó chạy block `export_zone_lookup` cùng các upstream block. Pipeline đọc `data/reference/taxi_zone_lookup.csv` và nạp vào `stage.stg_taxi_zone_lookup`.

Chi tiết thao tác trên Mage UI được mô tả trong [staging/README.md](staging/README.md).

### 5. Nạp Yellow Taxi Trip Records

Mở pipeline `ingest_trips_to_postgres`. Mặc định biến `file_name` là `ALL`, nghĩa là pipeline xét các tháng 2024–2025.

Các biến pipeline được hỗ trợ:

| Biến | Ví dụ | Ý nghĩa |
|---|---|---|
| `file_name` | `yellow_tripdata_2024-01.parquet` | Chỉ nạp một file cụ thể |
| `file_name` | `ALL` | Xét toàn bộ các tháng trong phạm vi và bộ lọc |
| `year` | `2024` | Chỉ xét một năm |
| `start_month` | `2024-01` | Tháng bắt đầu |
| `end_month` | `2024-03` | Tháng kết thúc |
| `use_lset` | `true` | Bắt đầu từ tháng LSET liên tục cuối cùng; file đã thành công sẽ được bỏ qua |

Pipeline có thể tự tải các Parquet còn thiếu vào `data/raw/`; chạy script tải trước là tùy chọn:

```powershell
powershell -ExecutionPolicy Bypass -File data\download_raw.ps1
```

Để kiểm tra lịch sử nạp:

```powershell
docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging -c "SELECT source_file_name, rows_read, rows_loaded, status, started_at, finished_at FROM control.etl_control ORDER BY control_id;"
```

Pipeline nạp theo batch, thử lại khi mở kết nối PostgreSQL hoặc tải file, ghi log trạng thái theo file và tiếp tục xét các file còn lại khi một file lỗi. Nếu kết nối bị gián đoạn trong lúc nạp, giao dịch của file đó sẽ thất bại; xem log `FAILED`, xử lý nguyên nhân rồi chạy lại pipeline để nạp lại file. Không chạy đồng thời nhiều lượt nạp trên cùng một file.

> Hướng dẫn đầy đủ về biến Mage, kiểm tra dữ liệu, SQL profiling, chạy lại và xử lý sự cố nằm trong [staging/README.md](staging/README.md).

## Kiểm tra dữ liệu Staging

Các truy vấn kiểm tra dữ liệu đặt tại `staging/pg_checks/`. Chạy truy vấn bằng PowerShell, ví dụ:

```powershell
Get-Content staging\pg_checks\03_profile_by_vendor.sql | docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging
```

Một số truy vấn cần tham số hoặc tùy chọn `psql`; xem phần tương ứng trong [staging/README.md](staging/README.md) trước khi chạy. Một số phép kiểm tra quét toàn bảng lớn và có thể mất vài phút.

Staging giữ dữ liệu nguồn và các cột kiểm toán; các bước làm sạch, lọc nghiệp vụ và mô hình hóa thuộc các tầng tiếp theo.

## dbt, DDS, OLAP và Power BI

Các thư mục `dbt/`, `warehouse/` và `powerbi/` hiện được tạo làm khung dự án. Repo hiện chưa có `dbt_project.yml`, `profiles.yml`, model dbt, các package hoặc project Power BI hoàn chỉnh. Vì vậy, các lệnh như `dbt deps`, `dbt run` và `dbt test` **chưa thể chạy trong trạng thái repo hiện tại**.

Khi các phần này được triển khai, cần cập nhật README với cấu hình thực tế, cách kết nối tới PostgreSQL, lệnh chạy và kết quả kiểm thử.

## Cấu hình và lưu ý dữ liệu

- Dữ liệu thô trong `data/raw/`, file `.env`, file DuckDB và dữ liệu sinh ra của Mage không nên commit.
- PostgreSQL lưu dữ liệu trong Docker volume `pgdata`; `docker compose down` không xóa volume.
- Không dùng `docker compose down -v` trừ khi chủ động muốn xóa dữ liệu PostgreSQL cục bộ.
- Đổi mật khẩu trong `.env` không tự đổi mật khẩu đã được khởi tạo trong volume hiện có.
- Dữ liệu chuyến đi được nạp vào `stage.stg_yellow_taxi_trips`; nhật ký mỗi lần nạp được lưu trong `control.etl_control`.

## Quy trình làm việc với Git

Nhóm sử dụng các nhánh `main`, `develop` và nhánh tính năng `feat/<phạm-vi>-<tên>`. Không push trực tiếp lên `main` hoặc `develop`; tạo Pull Request từ nhánh tính năng vào `develop` để review.

```powershell
# Lấy code
git clone https://github.com/nguyenanhtuan2702/NYC_TAXI.git
Set-Location NYC_TAXI
git checkout develop
git checkout -b feat/staging-ten-cua-ban

# Cập nhật nhánh làm việc từ develop
git fetch origin
git merge origin/develop

# Kiểm tra và lưu thay đổi
git status
git add <duong-dan-file>
git commit -m "feat(staging): describe the change"
git push -u origin feat/staging-ten-cua-ban
```

Không dùng `git add .` một cách máy móc. Kiểm tra `git status` để tránh đưa `.env`, dữ liệu lớn, file sinh tự động hoặc thay đổi không thuộc phạm vi của mình vào commit.

### Quy ước commit gợi ý

```text
<type>(<scope>): <mô tả ngắn>
```

Một số type thường dùng: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`. Scope có thể là `staging`, `mage`, `dbt`, `dim`, `fact`, `olap`, `pbi` hoặc `report`.

## Phân công và lộ trình

Phân công dưới đây là định hướng làm việc của nhóm; cập nhật theo quyết định mới nhất của nhóm nếu có thay đổi.

| Phạm vi | Trách nhiệm dự kiến | Thư mục chính |
|---|---|---|
| Ingestion và Staging | Nạp nguồn, DDL, kiểm tra dữ liệu | `staging/`, `mage/data_loaders/`, `mage/data_exporters/`, `dbt/models/staging/` |
| Dimension | Xây dựng các bảng Dimension và dữ liệu danh mục | `dbt/seeds/`, `dbt/models/dds/dimensions/` |
| Fact và OLAP | Xây dựng bảng Fact và truy vấn phân tích | `dbt/models/dds/facts/`, `dbt/models/olap_marts/` |
| Kiểm thử và tích hợp | Test, pipeline end-to-end và tài liệu nhóm | `dbt/tests/`, `mage/pipelines/02_end_to_end_elt_pipeline/`, `docs/`, `README.md` |

Lộ trình hoàn thiện gồm: triển khai cấu hình và model dbt; xây dựng DDS/OLAP; tích hợp pipeline end-to-end; bổ sung kiểm thử; sau đó hoàn thiện Power BI và báo cáo. Chỉ đánh dấu các hạng mục là hoàn thành khi code và hướng dẫn chạy tương ứng đã có trong repo và được kiểm thử.

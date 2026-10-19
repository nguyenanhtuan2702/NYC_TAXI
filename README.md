# NYC Yellow Taxi Trip Data Warehouse & Analytics (2024–2025)

Dự án xây dựng hệ thống Kho dữ liệu (Data Warehouse), đường ống xử lý dữ liệu (ELT Pipeline) và phân tích OLAP/Dashboard cho bộ dữ liệu **NYC Yellow Taxi Trip (2024–2025)**.

## 1. Kiến trúc Kỹ thuật (Technical Stack)

Hệ thống được thiết kế theo mô hình **Modern Data Stack** kết hợp kiến trúc 3 tầng (**Source → Staging → DDS / Star Schema**):

| Tầng xử lý | Công cụ | Vai trò trong dự án |
| :--- | :--- | :--- |
| **Data Sources** | CSV / Parquet / Shapefile | 3 nguồn dữ liệu chính: `Yellow Taxi Trip Records` (2024–2025), `Taxi Zone Lookup` (CSV), và `Taxi Zone Boundaries` (Shapefile ZIP). |
| **Data Ingestion & Orchestration** | **Mage.ai** | Điều phối luồng đọc dữ liệu thô, kiểm tra định dạng sơ bộ, nạp vào PostgreSQL Staging và kích hoạt lệnh chạy `dbt`. |
| **Staging Database** | **PostgreSQL** | Lưu trữ dữ liệu bảng tạm (`stg_yellow_taxi_trips`, `stg_taxi_zone_lookup`) và bảng ghi log kiểm soát quá trình ETL (`etl_control`). |
| **Data Transformation & Testing** | **dbt (`dbt-duckdb`)** | Kết nối trực tiếp vào PostgreSQL Staging, làm sạch dữ liệu, sinh khóa thay thế (`Surrogate Key`), nạp vào 8 bảng Dimension, 1 bảng Fact và kiểm thử tự động (`dbt test`). |
| **Data Warehouse (DDS & OLAP)** | **DuckDB** | Lưu trữ mô hình **Star Schema** (`FactTaxiTrip` và 8 bảng `Dim*`) cùng hệ thống View phục vụ 8 câu truy vấn OLAP cơ bản (A1–A8) và 6 câu mở rộng (B1–B5b). |
| **BI & Visualization** | **Power BI (`.pbip`)** | Kết nối DuckDB, định nghĩa các **Semantic / Calculated Measures** bằng DAX (`AvgSpeed`, `AvgTipRate`, `RevenueGrowthRate`,...) và trực quan hóa Dashboard / Bản đồ không gian. |

## 2. Cấu trúc Cây Thư mục

```text
nyc-yellow-taxi-mds/
├── README.md                                        # Tài liệu hướng dẫn quy trình làm việc và sử dụng Git
├── docker-compose.yml                               # Khởi chạy Mage.ai + PostgreSQL
├── .env.example                                     # Biến môi trường mẫu
├── .gitignore                                       # Chặn file dữ liệu nặng (.csv, .parquet, .duckdb)
│
├── data/                                            # Quản lý dữ liệu nguồn
│   ├── raw/                                         # [Git Ignore] File CSV/Parquet gốc 2024-2025 tại máy cá nhân
│   ├── sample/                                      # [Commit] Dữ liệu mẫu nhỏ (1.000 - 10.000 dòng) để chạy thử
│   └── reference/                                   # [Commit] taxi_zone_lookup.csv & taxi_zones_shapefile.zip
│
├── postgres_staging/                                # [Người 1 - Vân] DDL tạo bảng Staging & kiểm tra nhanh trên Postgres
│   ├── init_sql/
│   └── pg_checks/
│
├── mage_nyc_taxi/                                   # [Người 1 - Vân & Người 4 - Bee] Pipelines điều phối Ingestion & E2E
│   ├── pipelines/
│   ├── data_loaders/
│   ├── transformers/
│   ├── data_exporters/
│   └── custom/
│
├── dbt_nyc_taxi/                                    # [Khoa, Thịnh, Bee] Transformation & Data Quality Tests
│   ├── dbt_project.yml
│   ├── packages.yml
│   ├── profiles.yml
│   ├── seeds/                                       # [Người 2 - Khoa] Danh mục tĩnh (Vendor, RateCode, PaymentType, Groups)
│   ├── macros/                                      # [Khoa & Thịnh] Macro sinh Surrogate Key & kết nối Postgres
│   ├── models/
│   │   ├── staging/                                 # [Người 1 - Vân] Khai báo sources & staging views từ Postgres
│   │   ├── dds/
│   │   │   ├── _dds__models.yml                     # [Bee, Khoa, Thịnh] Ràng buộc PK, FK, not_null, unique
│   │   │   ├── dimensions/                          # [Người 2 - Khoa] 8 bảng Dimension (DimDate, DimTime, DimLocation,...)
│   │   │   └── facts/                               # [Người 3 - Thịnh] Bảng FactTaxiTrip
│   │   └── olap_marts/                              # [Cả nhóm] Views phục vụ phân tích cơ bản (A1-A8) & mở rộng (B1-B5b)
│   └── tests/                                       # [Người 4 - Bee] Singular dbt tests kiểm tra chéo Staging - Dim - Fact
│
├── warehouse/                                       # [Git Ignore] Chứa file nyc_taxi_dwh.duckdb sinh ra khi chạy dbt
├── powerbi/                                         # [Cả nhóm] File Power BI Project (.pbip), mã DAX & bản đồ TopoJSON
└── docs/                                            # Tài liệu mapping, biên bản kiểm thử và báo cáo (Mốc 1/11 & 1/12)
```

## 3. Phân công Nhiệm vụ & Vùng Làm việc trên Git

Để không dẫm chân lên code của nhau và tránh xung đột khi gộp nhánh (Merge Conflict), mỗi thành viên chỉ chỉnh sửa trực tiếp các thư mục thuộc phạm vi phụ trách của mình:

| Thành viên | Vai trò chính | Nhánh làm việc (`Feature Branch`) | Thư mục phụ trách chính | Người Review & Chạy thử chéo (28/10) |
| :--- | :--- | :--- | :--- | :--- |
| **Người 1 (Vân)** | **Ingestion & Staging** (Source → Postgres Staging; Thống kê thời gian sau 1/11) | `feat/staging-van` | `postgres_staging/`, `mage_nyc_taxi/data_loaders/`, `mage_nyc_taxi/data_exporters/`, `dbt_nyc_taxi/models/staging/`, `docs/03_reports/sections/01_staging_survey_van.md` | **Khoa** |
| **Người 2 (Khoa)** | **Dimension Modeling** (Staging → 8 bảng Dim trên DuckDB; Truy vấn doanh thu/khu vực) | `feat/dimension-khoa` | `dbt_nyc_taxi/seeds/`, `dbt_nyc_taxi/models/dds/dimensions/`, `docs/03_reports/sections/02_dimension_design_khoa.md` | **Thịnh** |
| **Người 3 (Thịnh)** | **Fact & OLAP Modeling** (Staging + Dim → `FactTaxiTrip`; Truy vấn mở rộng) | `feat/fact-thinh` | `dbt_nyc_taxi/models/dds/facts/`, `dbt_nyc_taxi/models/olap_marts/`, `docs/03_reports/sections/03_fact_etl_thinh.md` | **Bee** |
| **Người 4 (Bee)** | **Testing, Orchestration & Docs** (Test plan, `dbt test`, tích hợp pipeline, tổng hợp báo cáo) | `feat/testing-bee` | `dbt_nyc_taxi/tests/`, `dbt_nyc_taxi/models/dds/_dds__models.yml`, `mage_nyc_taxi/pipelines/02_end_to_end_elt_pipeline/`, `docs/02_test_plans_and_logs/`, `README.md` | **Vân** |

## 4. Hướng dẫn Khởi chạy Nhanh (Local Setup)

### Bước 1: Chuẩn bị môi trường
1. Sao chép file biến môi trường mẫu:
   ```bash
   cp .env.example .env
   ```
   2. Tải 24 file Parquet Yellow Taxi 2024–2025 về `data/raw/` (chạy 1 lần, file đã có sẽ được bỏ qua; thư mục này bị `.gitignore` chặn nên không commit):
```powershell
      powershell -ExecutionPolicy Bypass -File data\download_raw.ps1
```
      Giai đoạn code thử (18–20/10) có thể dùng file mẫu trong `data/sample/`.

### Bước 2: Khởi động PostgreSQL Staging và Mage.ai
```bash
docker compose up -d
```
* Giao diện **Mage.ai**: truy cập tại `http://localhost:6789`
* CSDL **PostgreSQL Staging**: cổng `localhost:5432` (Database: `nyc_taxi_staging`)

### Bước 3: Chạy dbt xây dựng Star Schema trên DuckDB
Di chuyển vào thư mục `dbt_nyc_taxi` (hoặc chạy qua terminal của Mage.ai container):
```bash
cd dbt_nyc_taxi
dbt deps                                # Cài đặt gói dbt_utils
dbt seed                                # Nạp các bảng danh mục tĩnh (Vendor, RateCode, PaymentType, Groups)
dbt run --select staging                # Tạo các staging views kết nối PostgreSQL
dbt run --select tag:dimension          # Tạo 8 bảng Dimension trong DuckDB
dbt run --select tag:fact               # Tạo bảng FactTaxiTrip trong DuckDB
dbt test                                # Chạy toàn bộ bộ kiểm thử dữ liệu của Bee
```

## 5. Quy trình Làm việc với Git (Git Workflow)

Nhóm sử dụng mô hình **3 tầng nhánh** để đảm bảo nhánh nộp bài luôn chạy ổn định:
* **`main`**: Nhánh chính thức, chỉ chứa code đã kiểm thử hoàn chỉnh để đóng gói nộp bài vào mốc **1/11** và **1/12**. Không ai được push trực tiếp lên `main`.
* **`develop`**: Nhánh tích hợp chung của cả 4 thành viên. Khi hoàn thành một phần việc, thành viên tạo Pull Request (PR) gộp vào `develop`.
* **`feat/<ten-phan-viec>-<ten-thanh-vien>`**: Nhánh làm việc cá nhân của từng người (ví dụ: `feat/staging-van`, `feat/dimension-khoa`, `feat/fact-thinh`, `feat/testing-bee`).

### Các bước thao tác Git hàng ngày

#### 1. Lần đầu tiên lấy dự án về máy
```bash
git clone <URL_REPOSITORY_CUA_NHOM>
cd nyc-yellow-taxi-mds
git checkout develop
git checkout -b feat/staging-van        # Thay bằng tên nhánh của bạn
```

#### 2. Trước khi bắt đầu code mỗi ngày (Cập nhật code mới nhất từ nhóm)
Luôn kéo code mới nhất từ nhánh `develop` về nhánh cá nhân trước khi làm việc để tránh lệch cấu trúc bảng:
```bash
git checkout develop
git pull origin develop
git checkout feat/staging-van           # Quay lại nhánh cá nhân
git merge develop                       # Gộp cập nhật mới nhất từ develop vào nhánh của mình
```

#### 3. Khi code xong một tính năng / script và muốn lưu lên Git
```bash
# 1. Kiểm tra những file nào vừa bị thay đổi (đảm bảo không dính file dữ liệu nặng)
git status

# 2. Đưa các file cần lưu vào vùng chờ (Staging Area)
git add <duong-dan-file>
# Ví dụ: git add dbt_nyc_taxi/models/dds/dimensions/dim_location.sql

# 3. Tạo commit với nội dung rõ ràng theo chuẩn của nhóm
git commit -m "feat(dim): add dim_location model with surrogate key and unknown member"

# 4. Đẩy code từ máy cá nhân lên GitHub
git push origin feat/staging-van
```

#### 4. Tạo Pull Request (PR) để ghép code vào `develop`
1. Lên trang GitHub của nhóm, bấm **Compare & pull request** từ nhánh cá nhân (`feat/...`) vào nhánh **`develop`**.
2. Điền ngắn gọn trong phần mô tả PR:
   * **Input nhận vào**: (ví dụ: bảng `stg_yellow_taxi_trips` từ Postgres).
   * **Output tạo ra**: (ví dụ: bảng `dim_vendor`, `dim_rate_code` trong DuckDB).
   * **Cách chạy thử**: (ví dụ: `dbt run --select dim_vendor`).
3. Gắn thẻ (**Assign Reviewer**) thành viên phụ trách kiểm thử chéo theo bảng phân công ở Mục 3 để duyệt và nhấn **Merge pull request**.

## 6. Quy ước Đặt tên Commit (Commit Message Convention)

Để lịch sử Git sạch đẹp, dễ tra cứu khi ghép báo cáo và chấm điểm, toàn bộ thành viên thống nhất cấu trúc commit như sau:

```text
<loại_thay_đổi>(<phạm_vi>): <mô_tả_ngắn_gọn_việc_đã_làm>
```

### Danh sách `<loại_thay_đổi>` (Type)
* **`feat`**: Thêm mới bảng, pipeline Mage, model dbt, truy vấn OLAP hoặc biểu đồ Power BI.
* **`fix`**: Sửa lỗi kiểu dữ liệu, lỗi sai khóa ngoại, lỗi logic tính toán hoặc lỗi kết nối.
* **`test`**: Thêm hoặc cập nhật test plan, schema test (`.yml`) hoặc singular test (`.sql`).
* **`docs`**: Cập nhật tài liệu mapping, biên bản kiểm thử, phần báo cáo cá nhân hoặc `README.md`.
* **`chore`**: Cập nhật cấu hình `docker-compose.yml`, `.gitignore`, `packages.yml` hoặc `dbt_project.yml`.
* **`refactor`**: Tối ưu lại câu truy vấn SQL/dbt cho chạy nhanh hơn mà không làm đổi kết quả đầu ra.

### Danh sách `<phạm_vi>` (Scope) theo từng phần việc
* **`staging`** hoặc **`mage`**: Phần đọc dữ liệu nguồn và nạp PostgreSQL Staging (Vân).
* **`dim`**: Phần bảng Dimension và seed files (Khoa).
* **`fact`**: Phần bảng `FactTaxiTrip` (Thịnh).
* **`olap`**: Phần truy vấn phân tích cơ bản A1–A8 và mở rộng B1–B5b (Cả nhóm).
* **`test`** hoặc **`control`**: Phần kiểm thử dữ liệu và log ETL (Bee).
* **`pbi`**: Phần mô hình DAX và biểu đồ Power BI (Cả nhóm).
* **`report`**: Phần viết báo cáo mốc 1/11 và 1/12 (Cả nhóm).

### Ví dụ Commit chuẩn cho từng thành viên
* **Người 1 (Vân)**:
  * `feat(staging): create postgres DDL for stg_yellow_taxi_trips and zone lookup`
  * `feat(mage): add parquet loader and postgres exporter for 2024-2025 trips`
  * `docs(report): add source survey and staging verification section`
* **Người 2 (Khoa)**:
  * `feat(dim): add seed files for vendor, rate code, payment type and groups`
  * `feat(dim): implement dim_date and dim_time with hierarchy attributes`
  * `fix(dim): handle missing LocationID with -1 unknown surrogate key`
* **Người 3 (Thịnh)**:
  * `feat(fact): build fact_taxi_trip model with 11 dimension surrogate keys`
  * `fix(fact): filter invalid negative trip duration before calculating speed`
  * `feat(olap): add advanced views B01 to B04 for tip rate and revenue growth`
* **Người 4 (Bee)**:
  * `test(staging): add row count and timestamp null checks for postgres stage`
  * `test(fact): add reconciliation test between staging valid rows and fact table`
  * `docs(report): merge all 4 member sections for 01/11 milestone submission`

## 7. Năm Nguyên tắc Sống còn Khi Dùng Git Trong Nhóm

1. **Tuyệt đối không commit dữ liệu thô (`data/raw/`) và file `.duckdb`**: Trước khi gõ `git commit`, luôn chạy `git status` để chắc chắn không có file `.csv`, `.parquet` lớn hơn 50MB hay file `nyc_taxi_dwh.duckdb` nằm trong danh sách. Nếu lỡ `git add`, dùng lệnh `git reset <tên_file>` để gỡ ra ngay.
2. **Không dùng `git add .` một cách mù quáng**: Hãy dùng `git status` rồi `git add <đường_dẫn_thư_mục_của_bạn>` để tránh vô tình đẩy các file cấu hình tạm trên máy cá nhân lên kho chung.
3. **Không sửa trực tiếp file `.pbix` nhị phân cùng lúc**: Khi làm Power BI (giai đoạn 16–21/11), lưu dưới định dạng **Power BI Project (`.pbip`)** và tách công thức DAX vào thư mục `powerbi/dax/` để Git quản lý được từng dòng thay đổi.
4. **Ghi rõ số dòng bị lọc trong báo cáo & commit**: Khi viết logic lọc bỏ bản ghi không hợp lệ ở tầng Staging hoặc Fact (ví dụ: `fare_amount <= 0`, `dropoff < pickup`), phải ghi chú rõ điều kiện lọc trong file model và tài liệu `docs/02_test_plans_and_logs/` để kết quả đối chiếu của Bee khớp 100%.
5. **Không bao giờ dùng `git push --force` lên nhánh `develop` hoặc `main`**: Mọi xung đột (Conflict) cần được xử lý tại nhánh cá nhân bằng cách `git merge develop` và trao đổi trực tiếp với người liên quan.

## 8. Lộ trình Phối hợp & Các Mốc Kiểm tra Chung

| Thời gian | Mốc công việc trọng tâm | Đầu ra bắt buộc trên Git |
| :--- | :--- | :--- |
| **18–20/10** | Khởi tạo repo, thống nhất schema, chạy thử dữ liệu mẫu | Có đủ khung thư mục, `docker-compose.yml`, mapping tài liệu trong `docs/01_data_modeling/` và `test_plan.md`. |
| **21–23/10** | Triển khai code Staging, Dimension, chuẩn bị Fact & Test | Mỗi thành viên push script đầu tiên lên nhánh `feat/...`; họp 5–10 phút ngày **23/10** giải thích rõ input/output. |
| **24–25/10** | Bàn giao Staging & Dimension, nạp thử `FactTaxiTrip` | Vân và Khoa merge code ổn định vào `develop`; Thịnh kết nối tra cứu khóa Surrogate Key cho Fact. |
| **26–28/10** | Tích hợp toàn pipeline & Kiểm thử chéo (Cross-testing) | Ngày **28/10**: Đổi người chạy thử chéo (`Khoa chạy Stage`, `Thịnh chạy Dim`, `Bee chạy Fact`, `Vân chạy Test`). |
| **29–30/10** | Viết báo cáo cá nhân & Rà soát đồng bộ code – báo cáo | 4 thành viên push file báo cáo vào `docs/03_reports/sections/`; Bee tổng hợp và cả nhóm duyệt ngày **30/10**. |
| **31/10 – 01/11** | Đóng gói & Nộp bài **Mốc 1 (Data Modeling & ETL)** | Merge `develop` sang `main`, gắn tag `v1.0-milestone-01-11`, xuất PDF và đóng gói ZIP kiểm tra lần cuối. |
| **02/11 – 15/11** | Hoàn thiện ETL toàn bộ dữ liệu & Truy vấn OLAP | Hoàn chỉnh pipeline chạy lại tự động (8/11) và các view OLAP cơ bản/mở rộng trong `models/olap_marts/` (15/11). |
| **16/11 – 30/11** | Xây dựng Power BI Dashboard, Bản đồ & Báo cáo cuối kỳ | Hoàn thiện `powerbi/` (21/11), chốt báo cáo cuối kỳ (26/11), review chéo toàn hệ thống (30/11) và nộp bài (**1/12**). |

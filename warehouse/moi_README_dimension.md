# BÁO CÁO CẬP NHẬT TẦNG DIMENSION (DDS) & PHẢN HỒI KIỂM THỬ

**Ngày cập nhật:** 27/10/2026  
**Phạm vi:** Tầng Dimension (Schema `dds`)  
**Mục đích:** Tài liệu này ghi nhận các điều chỉnh kỹ thuật tại tầng Dimension dựa trên Báo cáo kiểm thử lần 1 (Run ID: 20261026T034420Z), làm rõ các thiết kế nghiệp vụ và cung cấp hướng dẫn thực thi chuẩn.

---

## 1. Ánh xạ vấn đề QA và Giải pháp Kỹ thuật

Các kịch bản DDL và DML đã được tái cấu trúc để đảm bảo tính an toàn dữ liệu, khả năng chạy lặp (idempotency) và độ bao phủ miền giá trị.

### 1.1. Lỗi 4.1: DDL có thao tác phá hủy bảng
*   **Vấn đề QA:** Việc sử dụng `DROP TABLE IF EXISTS ... CASCADE` có nguy cơ xóa toàn bộ dữ liệu Dimension và Fact phụ thuộc nếu chạy trên database đang vận hành.
*   **Giải pháp kỹ thuật:** Loại bỏ hoàn toàn lệnh `DROP`. Khởi tạo bảng bằng từ khóa kiểm tra tồn tại, đảm bảo cấu trúc và dữ liệu hiện hữu không bị ảnh hưởng khi chạy script nhiều lần.
*   **Code áp dụng:**
    ```sql
    CREATE TABLE IF NOT EXISTS dds.DimVendor (...)
    ```

### 1.2. Lỗi 4.2 & 4.6: Rủi ro lặp dữ liệu và thiếu khóa tự nhiên
*   **Vấn đề QA:** Lệnh `SELECT DISTINCT` không ngăn được việc chèn đè bản ghi cũ ở các lần nạp (load) tiếp theo. Khóa tự nhiên (Natural Key) chưa có ràng buộc tính duy nhất.
*   **Giải pháp kỹ thuật:** 
    1. Cấp ràng buộc `UNIQUE NOT NULL` cho toàn bộ các Natural Key tại bước DDL.
    2. Sử dụng mệnh đề `ON CONFLICT DO NOTHING` tại bước DML để hệ thống tự động bỏ qua các bản ghi đã tồn tại, đảm bảo tính Idempotent.
*   **Code áp dụng:**
    ```sql
    -- DDL:
    VendorID INT UNIQUE NOT NULL
    -- DML:
    INSERT INTO dds.DimVendor (...) SELECT ... 
    ON CONFLICT (VendorID) DO NOTHING;
    ```

### 1.3. Lỗi 4.3: Khoảng cách không phủ kín miền giá trị
*   **Vấn đề QA:** Bảng `DimDistanceGroup` bị hở khoảng giá trị (từ 1.99 đến 2.00) và không có mức trần cho các chuyến đi có cự ly cực đoan.
*   **Giải pháp kỹ thuật:** Chuyển đổi kiểu dữ liệu khoảng cách sang `NUMERIC(10,4)`. Nối liền các dải phân cách và nới rộng mức trần.
*   **Code áp dụng:**
    ```sql
    ('SHORT', 'Dưới 2 miles', 0.0000, 1.9999),
    ('MEDIUM', '2 đến 5 miles', 2.0000, 5.0000),
    ('LONG', 'Trên 5 miles', 5.0001, 999999.9999)
    ```

### 1.4. Lỗi 4.4: Nhóm hành khách giới hạn trần không phù hợp
*   **Vấn đề QA:** Cận trên của nhóm LARGE đang khóa ở 99, có nguy cơ rớt dữ liệu outlier.
*   **Giải pháp kỹ thuật:** Đẩy `MaxPassengers` lên mức 9999 để bao trọn mọi dữ liệu rác/outlier từ hệ thống nguồn.
*   **Code áp dụng:**
    ```sql
    ('LARGE', 'Nhóm từ 5 người trở lên', 5, 9999)
    ```

---

## 2. Làm rõ Logic Unknown (Mục 4.5 & Quyết định DEC-06)

Hệ thống hiện tại duy trì **hai lớp phòng vệ Unknown** để đảm bảo tính toàn vẹn của dữ liệu doanh thu khi tổng hợp Fact. Cơ chế này cần được áp dụng nhất quán ở các khâu tích hợp.

### Lớp 1: Khóa tự nhiên mang nhãn 'Unknown' (Tại bảng Dimension)
*   **Ngữ nghĩa:** Dành cho các giá trị **thực sự tồn tại** trong hệ thống nguồn, nhưng nằm ngoài danh mục quy chuẩn của TLC hoặc không hợp lệ về mặt nghiệp vụ (Ví dụ: `vendor_id` = 6, 7; `payment_type` = 0).
*   **Giải pháp lưu trữ:** Các mã này vẫn được cấp một bản ghi trong bảng Dimension với ID tự nhiên gốc, nhưng thuộc tính mô tả (Name) được chuẩn hóa thành `'Unknown'`.
*   **Tích hợp Fact:** Sử dụng phép `LEFT JOIN` với ID tự nhiên như bình thường.
*   **Ví dụ Code:**
    ```sql
    CASE 
        WHEN vendor_id = 1 THEN 'Creative Mobile Technologies'
        WHEN vendor_id = 2 THEN 'VeriFone Inc.'
        ELSE 'Unknown' -- Áp dụng cho các mã 6, 7...
    END AS VendorName
    ```

### Lớp 2: Dòng mồ côi Surrogate Key = -1 (Xử lý tại bảng Fact)
*   **Ngữ nghĩa:** Dành cho các giao dịch trong Stage mang **mã hoàn toàn không tồn tại** trong cấu trúc Dimension (hoặc bị NULL mà không có quy tắc fallback), dẫn đến phép `LEFT JOIN` thất bại (trả về NULL).
*   **Giải pháp lưu trữ:** Mọi bảng Dimension đều được hardcode một bản ghi mặc định với Surrogate Key = `-1` và các giá trị tương ứng là `-1` hoặc `'Unknown'`.
*   **Tích hợp Fact:** BẮT BUỘC sử dụng hàm xử lý NULL để đẩy các bản ghi mồ côi này về dòng -1, ngăn chặn việc rớt dữ liệu doanh thu.
*   **Ví dụ Code (Dành cho Fact):**
    ```sql
    COALESCE(DimVendor.VendorSK, -1) AS VendorSK
    ```

---

## 3. Hướng dẫn thực thi và kiểm thử (Idempotent Run)

Kịch bản dưới đây thực thi toàn bộ pipeline Dimension và tuân thủ yêu cầu bắt lỗi nghiêm ngặt (QA-4.7).

**Môi trường yêu cầu:** 
- Container `nyc-postgres` trạng thái Healthy.
- CSDL `nyc_taxi_staging` đã được nạp dữ liệu Stage hợp lệ.

### Bước 1: Dọn dẹp Schema (Áp dụng khi cần Reset môi trường Test)
*Lưu ý: Chỉ thực hiện trên môi trường Test để xác minh khả năng khởi tạo DDL.*
```powershell
docker compose exec -T postgres psql -U taxi_user -d nyc_taxi_staging -c "DROP SCHEMA IF EXISTS dds CASCADE;"
```

### Bước 2: Khởi tạo cấu trúc và dòng Unknown
Sử dụng tham số `-v ON_ERROR_STOP=1` để dừng script ngay khi có ngoại lệ.
```powershell
Get-Content warehouse\01_create_dimensions.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U taxi_user -d nyc_taxi_staging
```

### Bước 3: Nạp và chuẩn hóa dữ liệu
```powershell
Get-Content warehouse\02_load_dimensions.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U taxi_user -d nyc_taxi_staging
```

### Kịch bản kiểm tra Idempotency
- **Hành động:** Chạy lại `Bước 3` nhiều lần liên tiếp.
- **Kỳ vọng:** Database không phát sinh lỗi `Duplicate Key`. Màn hình console trả về `INSERT 0 0` cho toàn bộ các khối truy vấn, xác nhận không có bản ghi trùng lặp nào được thêm vào.
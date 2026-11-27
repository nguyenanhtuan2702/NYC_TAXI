-- Mỗi file phải có source_row_number chạy liên tục 1..N, không trùng, không thiếu.
-- Ingestion sinh source_row_number = file_row_number + 1 nên điều kiện trên luôn đúng
-- nếu mỗi file được nạp đúng một lần.
--
-- Kiểm tra theo từng file bằng min = 1, max = N, sum = N(N+1)/2 thay vì GROUP BY
-- (source_file_name, source_row_number): kết quả tương đương với các lỗi thực tế
-- (nạp trùng file làm count gấp đôi; mất/thừa dòng làm lệch max hoặc sum), nhưng không cần
-- bảng băm ~90 triệu khóa (đo ngày 18/11/2026: 122 s -> dưới 1 s).
-- PASS khi không trả về dòng nào.
select
    source_file_name,
    count(*)                    as so_dong,
    min(source_row_number)      as rn_min,
    max(source_row_number)      as rn_max,
    sum(source_row_number)      as rn_sum
from {{ ref('stg_yellow_taxi_trips') }}
group by 1
having min(source_row_number) <> 1
    or max(source_row_number) <> count(*)
    or sum(source_row_number) <> count(*)::hugeint * (count(*) + 1) / 2

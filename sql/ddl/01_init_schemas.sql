-- DuckDB. Các block ingestion của Mage chạy lần lượt mọi file trong sql/ddl/ trước khi nạp,
-- nên mọi câu lệnh phải chạy lại được nhiều lần (IF NOT EXISTS).
-- raw     : dữ liệu nguồn nguyên trạng + cột kiểm toán (do Mage nạp)
-- control : log các lần nạp
-- stage, dds, olap do dbt tạo.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS control;

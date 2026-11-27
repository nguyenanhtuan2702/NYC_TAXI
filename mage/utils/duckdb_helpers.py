"""Hàm dùng chung cho các block ingestion ghi vào DuckDB.

Cấu hình lấy từ biến môi trường do docker-compose.yml đặt:
DUCKDB_PATH, DUCKDB_MEMORY_LIMIT, DUCKDB_THREADS, DUCKDB_TEMP_DIR.
"""
import glob
import os
import re
import time
from datetime import datetime

import duckdb

DDL_DIR = os.environ.get('DDL_DIR', '/home/src/sql/ddl')


def connect(max_retries=5, delay=2):
    """Mở file DuckDB để ghi.

    DuckDB chỉ cho một tiến trình ghi; nếu file đang bị khóa (dbt, DBeaver, Power BI,
    một lượt chạy Mage khác) thì thử lại với thời gian chờ tăng gấp đôi: 2s, 4s, 8s, 16s.
    """
    path = os.environ['DUCKDB_PATH']
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(1, max_retries + 1):
        try:
            con = duckdb.connect(path)
            break
        except duckdb.IOException as e:
            if 'lock' not in str(e).lower():
                raise
            if attempt == max_retries:
                raise RuntimeError(
                    f'File DuckDB đang bị tiến trình khác khóa sau {max_retries} lần thử: {e}')
            wait = delay * (2 ** (attempt - 1))
            print(f'[RETRY] DuckDB đang bị khóa (lần {attempt}/{max_retries}), thử lại sau {wait}s...')
            time.sleep(wait)

    memory_limit = os.environ.get('DUCKDB_MEMORY_LIMIT', '4GB')
    threads = os.environ.get('DUCKDB_THREADS', '4')
    temp_dir = os.environ.get('DUCKDB_TEMP_DIR')
    if not re.fullmatch(r'\d+(\.\d+)?\s*[KMGT]i?B', memory_limit, re.IGNORECASE):
        raise ValueError(f'DUCKDB_MEMORY_LIMIT không hợp lệ: {memory_limit!r}')
    con.execute(f"SET memory_limit = '{memory_limit}'")
    con.execute(f'SET threads = {int(threads)}')
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        con.execute("SET temp_directory = ?", [temp_dir])
    return con


def init_schema(con):
    """Chạy lần lượt các file sql/ddl/*.sql (đều idempotent)."""
    files = sorted(glob.glob(os.path.join(DDL_DIR, '*.sql')))
    if not files:
        raise FileNotFoundError(f'Không tìm thấy file DDL trong {DDL_DIR}')
    for f in files:
        with open(f, encoding='utf-8') as fh:
            con.execute(fh.read())


def next_batch_id(con):
    """batch_id dạng YYYYMMDDHHMMSS, luôn lớn hơn batch_id đã ghi trong log.

    Fact incremental lấy các dòng có batch_id > max(batch_id) đã nạp, nên giá trị phải tăng dần,
    kể cả khi hai lần nạp xảy ra trong cùng một giây.
    """
    candidate = int(datetime.now().strftime('%Y%m%d%H%M%S'))
    last = con.execute('SELECT max(batch_id) FROM control.etl_control').fetchone()[0]
    return max(candidate, (last or 0) + 1)


def write_log(con, pipeline_name, batch_id, file_name, cet, rows_read, rows_loaded,
              status, error_message, started_at):
    rejected = (rows_read - rows_loaded) if rows_read is not None else None
    con.execute(
        'INSERT INTO control.etl_control (pipeline_name, batch_id, source_file_name, '
        'last_extract_time, rows_read, rows_loaded, rows_rejected, status, error_message, '
        'started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [pipeline_name, batch_id, file_name, cet, rows_read, rows_loaded, rejected,
         status, error_message, started_at, datetime.now()])

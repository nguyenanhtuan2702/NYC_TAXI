"""Chạy SQL đọc từ stdin trên file DuckDB của dự án, chế độ chỉ đọc.

Dùng bởi `tasks.ps1 sql` và `tasks.ps1 profile`. Chạy lần lượt từng câu lệnh và in kết quả
của mọi câu SELECT (không chỉ câu cuối). Hỗ trợ `SET VARIABLE x = ...; ... getvariable('x')`.

    docker compose exec -T mage python /home/src/sql/run_sql.py < file.sql
"""
import os
import sys

import duckdb


def main():
    sql = sys.stdin.read()
    if not sql.strip():
        sys.exit('Không có câu SQL nào trên stdin.')
    con = duckdb.connect(os.environ['DUCKDB_PATH'], read_only=True)
    con.execute('SET enable_progress_bar = false')
    statements = con.extract_statements(sql)
    for i, st in enumerate(statements, 1):
        rel = con.sql(st.query)
        if rel is None:          # SET, PRAGMA... không trả bảng
            continue
        if len(statements) > 1:
            print(f'-- [{i}/{len(statements)}]')
        rel.show(max_rows=200, max_width=300)
    con.close()


if __name__ == '__main__':
    main()

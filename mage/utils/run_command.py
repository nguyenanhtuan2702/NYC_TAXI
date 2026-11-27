"""Chạy một lệnh ngoài (dbt, runner QA, script xuất Power BI) từ block Mage.

In từng dòng output ngay khi có (log của block hiện tiến độ), trả về mã thoát.
Các bước này chạy tuần tự sau khi block ingestion đã đóng kết nối DuckDB, nên tiến trình
con là tiến trình duy nhất mở file DuckDB (DuckDB chỉ cho một tiến trình ghi).
"""
import os
import subprocess
import time


def run_command(args, cwd='/home/src', env=None):
    started = time.monotonic()
    print(f'[RUN] {" ".join(args)}')
    merged_env = {**os.environ, **(env or {}), 'PYTHONUNBUFFERED': '1'}
    proc = subprocess.Popen(args, cwd=cwd, env=merged_env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    for line in proc.stdout:
        print(line.rstrip())
    code = proc.wait()
    print(f'[EXIT {code}] {args[0]} sau {time.monotonic() - started:,.0f} s')
    return code

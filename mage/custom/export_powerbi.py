"""Bước cuối của pipeline nyc_taxi_e2e: xuất OLAP mart + Dimension ra data/bi/*.parquet.

Power BI đọc các file này (không đọc file DuckDB). Script mở DuckDB read_only và ghi từng
file qua file tạm rồi mới đổi tên, nên Power BI không đọc phải file đang ghi dở.
"""
try:
    from mage.utils.run_command import run_command
except ImportError:  # khi Mage đặt thư mục project làm gốc import
    from utils.run_command import run_command

if 'custom' not in globals():
    from mage_ai.data_preparation.decorators import custom


@custom
def export_powerbi(*args, **kwargs):
    code = run_command(['python', '/home/src/powerbi/scripts/export_bi.py'])
    if code != 0:
        raise RuntimeError(f'Xuất Parquet cho Power BI thất bại (mã {code})')

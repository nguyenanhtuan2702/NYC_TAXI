"""Bước ELT của pipeline nyc_taxi_e2e: dbt build (snapshot, staging, Dimension, Fact, OLAP mart, test).

dbt cài trong venv riêng /opt/dbt (không cài vào môi trường Python của Mage), nên gọi bằng
subprocess thay vì block dbt có sẵn của Mage. Fact là incremental delete+insert theo
sourcefilename: tháng không có batch mới thì không bị nạp lại.

Biến pipeline: dbt_select (tùy chọn, vd "olap_marts"; mặc định build toàn bộ project).
"""
try:
    from mage.utils.run_command import run_command
except ImportError:  # khi Mage đặt thư mục project làm gốc import
    from utils.run_command import run_command

if 'custom' not in globals():
    from mage_ai.data_preparation.decorators import custom

DBT = '/opt/dbt/bin/dbt'
PROJECT_DIR = '/home/src/dbt'


@custom
def run_dbt_build(*args, **kwargs):
    cmd = [DBT, 'build', '--project-dir', PROJECT_DIR, '--profiles-dir', PROJECT_DIR]
    select = kwargs.get('dbt_select')
    if select:
        cmd += ['--select', str(select)]
    code = run_command(cmd, cwd=PROJECT_DIR)
    if code != 0:
        raise RuntimeError(f'dbt build thất bại (mã {code}); xem log ở trên hoặc dbt/logs/dbt.log')

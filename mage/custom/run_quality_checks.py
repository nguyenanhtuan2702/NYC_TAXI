"""Bước QA của pipeline nyc_taxi_e2e: runner QA chỉ đọc (tests/run_quality_tests.py).

Runner mở DuckDB ở chế độ read_only và ghi kết quả vào docs/test_plans_and_logs/runs/.
Mã thoát: 0 = PASS; 1 = có FAIL (dừng pipeline, không xuất dữ liệu sai cho Power BI);
2 = có BLOCKED (chỉ cảnh báo, vẫn chạy tiếp).

Biến pipeline: qa_suite (smoke | deep | all, mặc định all), qa_large_scans (true/false, mặc định false).
"""
try:
    from mage.utils.run_command import run_command
except ImportError:  # khi Mage đặt thư mục project làm gốc import
    from utils.run_command import run_command

if 'custom' not in globals():
    from mage_ai.data_preparation.decorators import custom


@custom
def run_quality_checks(*args, **kwargs):
    suite = str(kwargs.get('qa_suite') or 'all')
    # argparse thoát mã 2 khi tham số sai, trùng mã 2 "có BLOCKED": kiểm tra trước để không bị bỏ qua.
    if suite not in ('preflight', 'smoke', 'deep', 'all'):
        raise ValueError(f'qa_suite không hợp lệ: {suite!r} (preflight | smoke | deep | all)')
    cmd = ['python', '/home/src/tests/run_quality_tests.py', '--suite', suite]
    if str(kwargs.get('qa_large_scans', False)).strip().lower() in ('1', 'true', 'yes'):
        cmd.append('--include-large-scans')
    code = run_command(cmd)
    if code == 1:
        raise RuntimeError('QA có kiểm tra FAIL: dừng pipeline trước khi xuất dữ liệu cho Power BI')
    if code == 2:
        print('[QA WARN] có kiểm tra BLOCKED; vẫn chạy tiếp')
    elif code != 0:
        raise RuntimeError(f'Runner QA lỗi (mã {code})')

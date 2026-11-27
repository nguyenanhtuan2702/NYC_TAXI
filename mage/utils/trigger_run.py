"""Chạy tay pipeline nyc_taxi_e2e qua scheduler của Mage (trigger API `manual_e2e`) và đợi kết quả.

Khác `mage run` (chạy thẳng, không qua BlockExecutor): lượt chạy tạo bằng script này đi đúng đường
của lượt theo lịch, nên có retry_config, callback cảnh báo khi lỗi, timeout của trigger và hiện
trong lịch sử trên giao diện Mage. Cần server Mage đang chạy (container nyc-mage).

Dùng (trong container, qua `.\\tasks.ps1 e2e [JSON biến ghi đè]`):
    python /home/src/mage/utils/trigger_run.py '{"qa_suite": "smoke"}'
Mã thoát: 0 = completed; 1 = failed/cancelled; 2 = không tạo được lượt chạy.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

PIPELINE_UUID = 'nyc_taxi_e2e'
TRIGGER_NAME = 'manual_e2e'
POLL_SECONDS = 5
MAX_WAIT_SECONDS = 3 * 3600


def norm(status):
    """'ScheduleStatus.ACTIVE' / 'ACTIVE' / 'active' -> 'active'."""
    return str(getattr(status, 'value', status)).split('.')[-1].lower()


def main() -> int:
    overrides = json.loads(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].strip() else {}

    # Phải đặt repo path TRƯỚC khi import tầng DB của Mage (giống `mage run`), nếu không Mage tạo
    # một file SQLite trống theo thư mục hiện tại thay vì dùng mage_data/mage/mage-ai.db của server.
    from mage_ai.settings.repo import set_repo_path
    set_repo_path(os.environ.get('USER_CODE_PATH', '/home/src/mage'))

    from mage_ai.orchestration.db import db_connection
    from mage_ai.orchestration.db.models.schedules import BlockRun, PipelineRun, PipelineSchedule
    db_connection.start_session()

    schedule = PipelineSchedule.query.filter(
        PipelineSchedule.pipeline_uuid == PIPELINE_UUID,
        PipelineSchedule.name == TRIGGER_NAME,
    ).first()
    if schedule is None or norm(schedule.status) != 'active':
        print(f'Không có trigger {TRIGGER_NAME} đang active cho {PIPELINE_UUID} '
              f'(xem mage/pipelines/{PIPELINE_UUID}/triggers.yaml; khởi động lại container để Mage đọc lại).')
        return 2

    run = PipelineRun.create(
        pipeline_schedule_id=schedule.id,
        pipeline_uuid=PIPELINE_UUID,
        execution_date=datetime.now(timezone.utc),
        status=PipelineRun.PipelineRunStatus.INITIAL,
        variables=overrides,
    )
    print(f'Đã tạo lượt chạy {run.id} (trigger {TRIGGER_NAME}); scheduler của Mage sẽ thực thi. '
          f'Biến ghi đè: {overrides or "không"}')

    started = time.monotonic()
    printed = set()
    final = ('completed', 'failed', 'cancelled')
    while True:
        db_connection.session.expire_all()
        run = PipelineRun.query.get(run.id)
        for br in BlockRun.query.filter(BlockRun.pipeline_run_id == run.id).all():
            status = norm(br.status)
            if br.block_uuid not in printed and status in ('completed', 'failed', 'upstream_failed', 'cancelled'):
                printed.add(br.block_uuid)
                print(f'[{time.monotonic() - started:6.0f} s] {br.block_uuid}: {status}')
                if status == 'failed':
                    try:
                        content = (br.logs or {}).get('content') or ''
                        print('\n'.join(content.splitlines()[-25:]))
                    except Exception as e:
                        print(f'(không đọc được log: {e})')
        status = norm(run.status)
        if status in final:
            print(f'Lượt chạy {run.id}: {status} sau {time.monotonic() - started:,.0f} s')
            return 0 if status == 'completed' else 1
        if time.monotonic() - started > MAX_WAIT_SECONDS:
            print(f'Hết thời gian chờ; lượt chạy {run.id} vẫn ở trạng thái {status}')
            return 1
        time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    sys.exit(main())

"""Callback của pipeline nyc_taxi_e2e: block nào lỗi thì ghi cảnh báo và gửi webhook (mage/utils/alerts.py).

Gắn vào các block qua mục `callbacks` trong metadata.yaml của pipeline (upstream_blocks = các block
được theo dõi). Mage gọi hàm failure với lỗi trong kwargs['__error'], một lần sau khi block đã hết
số lần retry. Callback chỉ chạy trong lượt chạy qua scheduler (trigger), không chạy với `mage run`.
"""
try:
    from mage.utils.alerts import send_alert
except ImportError:  # khi Mage đặt thư mục project làm gốc import
    from utils.alerts import send_alert

if 'callback' not in globals():
    from mage_ai.data_preparation.decorators import callback


@callback('failure')
def notify_pipeline_failure(*args, **kwargs):
    error = kwargs.get('__error', 'không rõ lỗi')
    pipeline = kwargs.get('pipeline_uuid') or 'nyc_taxi_e2e'
    # block_uuid trong kwargs là chính callback; block bị lỗi nằm ở parent_block_uuid.
    block = kwargs.get('parent_block_uuid') or kwargs.get('block_uuid') or '?'
    run = kwargs.get('pipeline_run')
    run_info = {'pipeline_run_id': getattr(run, 'id', None) or kwargs.get('pipeline_run_id'),
                'execution_date': kwargs.get('execution_date')}
    send_alert(pipeline, block, error, run_info)

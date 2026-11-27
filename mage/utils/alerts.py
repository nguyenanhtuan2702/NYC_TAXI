"""Cảnh báo khi pipeline lỗi: ghi file + gửi webhook (nếu có).

- Luôn ghi một dòng JSON vào data/warehouse/alerts/pipeline_alerts.jsonl (xem nhanh bằng
  `.\\tasks.ps1 status`). Ghi file, không ghi DuckDB: lỗi có thể chính là file DuckDB đang bị khóa.
- Nếu biến môi trường ALERT_WEBHOOK_URL có giá trị: POST JSON {"text": ..., "content": ...}
  (khớp incoming webhook của Slack, Discord và Microsoft Teams/Power Automate dạng đơn giản).
- Mage gọi callback lỗi một lần sau khi block hết số lần retry. Để không gửi dồn khi chạy lại
  liên tục, cùng pipeline + block trong DEDUP_MINUTES chỉ gửi webhook một lần; file vẫn ghi đủ.
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

ALERT_DIR = os.environ.get('ALERT_DIR', '/home/src/data/warehouse/alerts')
ALERT_FILE = os.path.join(ALERT_DIR, 'pipeline_alerts.jsonl')
DEDUP_MINUTES = 60


def _recent_duplicate(pipeline, block, now):
    if not os.path.exists(ALERT_FILE):
        return False
    with open(ALERT_FILE, encoding='utf-8') as fh:
        lines = fh.readlines()[-50:]
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get('pipeline') == pipeline and rec.get('block') == block and rec.get('webhook_sent'):
            sent = datetime.fromisoformat(rec['at_utc'])
            return now - sent < timedelta(minutes=DEDUP_MINUTES)
    return False


def send_alert(pipeline, block, error, run_info=None):
    now = datetime.now(timezone.utc)
    message = (f'[NYC Taxi] Pipeline {pipeline} lỗi ở block {block} lúc '
               f'{now:%Y-%m-%d %H:%M} UTC: {str(error)[:500]}')
    print(f'[ALERT] {message}')

    url = os.environ.get('ALERT_WEBHOOK_URL', '').strip()
    sent, webhook_error = False, None
    if url and not _recent_duplicate(pipeline, block, now):
        try:
            body = json.dumps({'text': message, 'content': message}).encode('utf-8')
            req = urllib.request.Request(url, data=body, method='POST',
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=15):
                sent = True
        except Exception as e:  # cảnh báo không được làm hỏng thêm pipeline
            webhook_error = str(e)[:200]
            print(f'[ALERT WARN] gửi webhook thất bại: {webhook_error}')

    os.makedirs(ALERT_DIR, exist_ok=True)
    record = {'at_utc': now.isoformat(), 'pipeline': pipeline, 'block': block,
              'error': str(error)[:2000], 'webhook_sent': sent, 'webhook_error': webhook_error,
              **(run_info or {})}
    with open(ALERT_FILE, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')

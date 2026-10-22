import gc
import io
import os
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime

import psycopg2
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

RAW_DIR = '/home/src/data/raw'
BASE_URL = 'https://d37ci6vzurychx.cloudfront.net/trip-data'
TABLE = 'stage.stg_yellow_taxi_trips'
PIPELINE_NAME = 'ingest_trips_to_postgres'
BATCH_SIZE = 200_000
FIRST_MONTH = '2024-01'

RENAME = {'VendorID': 'vendor_id', 'RatecodeID': 'ratecode_id',
          'PULocationID': 'pu_location_id', 'DOLocationID': 'do_location_id',
          'Airport_fee': 'airport_fee'}
TARGET = ['vendor_id', 'tpep_pickup_datetime', 'tpep_dropoff_datetime',
          'passenger_count', 'trip_distance', 'ratecode_id',
          'store_and_fwd_flag', 'pu_location_id', 'do_location_id',
          'payment_type', 'fare_amount', 'extra', 'mta_tax', 'tip_amount',
          'tolls_amount', 'improvement_surcharge', 'total_amount',
          'congestion_surcharge', 'airport_fee', 'cbd_congestion_fee']
AUDIT = ['source_file_name', 'source_row_number', 'batch_id']


def to_bool(v):
    return str(v).strip().lower() in ('1', 'true', 'yes', 'y')


def get_db_connection(max_retries=5, delay=2):
    """Retry kết nối Postgres, thời gian chờ tăng gấp đôi: 2s, 4s, 8s, 16s."""
    for attempt in range(1, max_retries + 1):
        try:
            return psycopg2.connect(
                host=os.environ['POSTGRES_HOST'], port=os.environ['POSTGRES_PORT'],
                dbname=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'],
                password=os.environ['POSTGRES_PASSWORD'], connect_timeout=10)
        except Exception as e:
            if attempt == max_retries:
                raise RuntimeError(f'Không kết nối được PostgreSQL sau {max_retries} lần: {e}')
            wait = delay * (2 ** (attempt - 1))
            print(f'[RETRY] Kết nối Postgres lỗi (lần {attempt}/{max_retries}), thử lại sau {wait}s...')
            time.sleep(wait)


def write_log(batch_id, file_name, cet, rows_read, loaded, status, err, started):
    """Ghi log bằng connection MỚI để vẫn ghi được khi connection nạp dữ liệu đã chết."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO control.etl_control (pipeline_name, batch_id, source_file_name, '
            'last_extract_time, rows_read, rows_loaded, rows_rejected, status, '
            'error_message, started_at, finished_at) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (PIPELINE_NAME, batch_id, file_name, cet, rows_read, loaded,
             (rows_read - loaded) if rows_read is not None else None,
             status, err, started, datetime.now()))
        conn.commit()
    finally:
        conn.close()


def download_file_with_retry(file_name, max_retries=3):
    """Trả về (ok, lý do). Tải vào .tmp, đủ 100% mới đổi tên."""
    os.makedirs(RAW_DIR, exist_ok=True)
    target = os.path.join(RAW_DIR, file_name)
    if os.path.exists(target):
        return True, None
    tmp = target + '.tmp'
    url = f'{BASE_URL}/{file_name}'
    last = None
    for attempt in range(1, max_retries + 1):
        print(f'[DOWNLOAD] {file_name} (lần {attempt}/{max_retries})...')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, 'wb') as out:
                shutil.copyfileobj(resp, out)
            os.replace(tmp, target)
            print(f'[DOWNLOAD OK] {file_name}')
            return True, None
        except urllib.error.HTTPError as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            last = f'HTTP {e.code}: {e.reason}'
            if e.code in (403, 404):
                print(f'[DOWNLOAD] {file_name}: nguồn chưa có ({last})')
                return False, last
        except Exception as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            last = str(e)
        print(f'[DOWNLOAD WARN] {file_name}: {last}')
        time.sleep(3 * (2 ** (attempt - 1)))
    return False, f'Tải thất bại sau {max_retries} lần: {last}'


def load_one(file_name, cet=None):
    started = datetime.now()
    cet = cet or started
    batch_id = int(started.strftime('%Y%m%d%H%M%S'))

    ok, reason = download_file_with_retry(file_name)
    if not ok:
        write_log(batch_id, file_name, cet, None, 0, 'FAILED', f'DOWNLOAD: {reason}', started)
        raise RuntimeError(f'{file_name}: {reason}')

    pf = pq.ParquetFile(os.path.join(RAW_DIR, file_name))
    rows_read = pf.metadata.num_rows
    cols = ', '.join(TARGET + AUDIT)

    conn = get_db_connection()
    cur = conn.cursor()
    loaded, status, err = 0, 'SUCCESS', None
    try:
        # Chỉ DELETE khi file từng được nạp (có log), tránh quét 90M dòng vô ích
        cur.execute('SELECT 1 FROM control.etl_control WHERE source_file_name = %s LIMIT 1',
                    (file_name,))
        if cur.fetchone():
            cur.execute(f'DELETE FROM {TABLE} WHERE source_file_name = %s', (file_name,))
        for batch in pf.iter_batches(batch_size=BATCH_SIZE):
            t = pa.Table.from_batches([batch])
            t = t.rename_columns([RENAME.get(c, c) for c in t.column_names])
            n = t.num_rows
            for c in TARGET:
                if c not in t.column_names:
                    t = t.append_column(c, pa.nulls(n, pa.float64()))
            t = t.select(TARGET)
            t = t.append_column('source_file_name', pa.array([file_name] * n))
            t = t.append_column('source_row_number',
                                pa.array(range(loaded + 1, loaded + n + 1), pa.int64()))
            t = t.append_column('batch_id', pa.array([batch_id] * n, pa.int64()))
            buf = io.BytesIO()
            pacsv.write_csv(t, buf, pacsv.WriteOptions(include_header=False))
            buf.seek(0)
            cur.copy_expert(f'COPY {TABLE} ({cols}) FROM STDIN WITH (FORMAT csv)', buf)
            loaded += n
            del t, buf
            gc.collect()
        conn.commit()
    except Exception as e:
        status, err, loaded = 'FAILED', str(e)[:2000], 0
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    write_log(batch_id, file_name, cet, rows_read, loaded, status, err, started)
    print(f'[{status}] {file_name} | đọc {rows_read:,} | nạp {loaded:,} | {err}')
    if status == 'FAILED':
        raise RuntimeError(err)


def get_lset_month(cur):
    """LSET = tháng dữ liệu cuối cùng của dãy tháng liên tục, nạp thành công, tính từ FIRST_MONTH."""
    cur.execute("SELECT DISTINCT source_file_name FROM control.etl_control "
                "WHERE status='SUCCESS' AND rows_read = rows_loaded")
    done = {r[0] for r in cur.fetchall()}
    y, m = map(int, FIRST_MONTH.split('-'))
    last = None
    while f'yellow_tripdata_{y}-{m:02d}.parquet' in done:
        last = f'{y}-{m:02d}'
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return last, done


@data_exporter
def load_trips_to_stage(*args, **kwargs):
    file_name = kwargs.get('file_name')
    year = kwargs.get('year')
    start_month = kwargs.get('start_month')
    end_month = kwargs.get('end_month')
    use_lset = to_bool(kwargs.get('use_lset', False))

    cet = datetime.now()

    if file_name and file_name != 'ALL':
        load_one(file_name, cet=cet)
        return

    conn = get_db_connection()
    cur = conn.cursor()
    lset_month, done = get_lset_month(cur)
    conn.close()
    print(f'[ETL CONTROL] LSET (tháng dữ liệu liên tục cuối) = {lset_month} | CET = {cet}')

    months = [f'{y}-{m:02d}' for y in (2024, 2025) for m in range(1, 13)]
    if year:
        months = [m for m in months if m.startswith(str(year))]
    if use_lset and not (start_month or year) and lset_month:
        start_month = lset_month  # file cuối đã SUCCESS sẽ bị skip; tháng sau được nạp
    if start_month:
        months = [m for m in months if m >= str(start_month)]
    if end_month:
        months = [m for m in months if m <= str(end_month)]

    files = [f'yellow_tripdata_{m}.parquet' for m in months]
    print(f'Số file cần kiểm tra: {len(files)}')

    failed, skipped = [], []
    for f in files:
        if f in done:
            print(f'[SKIP] đã SUCCESS: {f}')
            continue
        try:
            load_one(f, cet=cet)
        except Exception as e:
            print(f'[FILE FAILED] {f}: {e}')
            failed.append(f)

    print(f'=== TỔNG KẾT: {len(files)} file | lỗi: {len(failed)} {failed}')
    if failed:
        raise RuntimeError(f'Còn {len(failed)} file chưa nạp được: {failed}')
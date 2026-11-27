"""Nạp Yellow Taxi Trip Records (Parquet) vào DuckDB: raw.yellow_tripdata.

- Tự tải file còn thiếu từ nguồn TLC vào data/raw (retry, tải vào .tmp rồi mới đổi tên).
- Mỗi file nạp trong một transaction: xóa các dòng cũ của file đó rồi INSERT lại, nên chạy lại không trùng.
- Ghi log từng file vào control.etl_control; LSET tính từ log này.
- Schema drift: file thiếu cột bắt buộc thì FAILED (không nạp NULL âm thầm); cột lạ thì cảnh báo.
- Phát hiện TLC phát hành lại file: so ETag/kích thước (HEAD) với control.source_file_meta;
  file đã SUCCESS nhưng nguồn đã đổi thì tải lại và nạp lại.

Biến pipeline: file_name (tên file hoặc ALL), year, start_month, end_month, use_lset,
check_source_updates (mặc định true), force_download (mặc định false: dùng file đã có trong data/raw).
"""
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime

try:
    from mage.utils.duckdb_helpers import connect, init_schema, next_batch_id, write_log
except ImportError:  # khi Mage đặt thư mục project làm gốc import
    from utils.duckdb_helpers import connect, init_schema, next_batch_id, write_log

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

RAW_DIR = os.environ.get('RAW_DATA_DIR', '/home/src/data/raw')
BASE_URL = 'https://d37ci6vzurychx.cloudfront.net/trip-data'
TABLE = 'raw.yellow_tripdata'
PIPELINE_NAME = 'ingest_yellow_trips'
FIRST_MONTH = '2024-01'
FILE_PATTERN = re.compile(r'yellow_tripdata_\d{4}-\d{2}\.parquet')

# Cột đích -> tên cột trong Parquet (so khớp không phân biệt hoa thường, vd Airport_fee).
TARGET = {
    'vendor_id': ('VendorID', 'INTEGER'),
    'tpep_pickup_datetime': ('tpep_pickup_datetime', 'TIMESTAMP'),
    'tpep_dropoff_datetime': ('tpep_dropoff_datetime', 'TIMESTAMP'),
    'passenger_count': ('passenger_count', 'BIGINT'),
    'trip_distance': ('trip_distance', 'DOUBLE'),
    'ratecode_id': ('RatecodeID', 'BIGINT'),
    'store_and_fwd_flag': ('store_and_fwd_flag', 'VARCHAR'),
    'pu_location_id': ('PULocationID', 'INTEGER'),
    'do_location_id': ('DOLocationID', 'INTEGER'),
    'payment_type': ('payment_type', 'BIGINT'),
    'fare_amount': ('fare_amount', 'DOUBLE'),
    'extra': ('extra', 'DOUBLE'),
    'mta_tax': ('mta_tax', 'DOUBLE'),
    'tip_amount': ('tip_amount', 'DOUBLE'),
    'tolls_amount': ('tolls_amount', 'DOUBLE'),
    'improvement_surcharge': ('improvement_surcharge', 'DOUBLE'),
    'total_amount': ('total_amount', 'DOUBLE'),
    'congestion_surcharge': ('congestion_surcharge', 'DOUBLE'),
    'airport_fee': ('airport_fee', 'DOUBLE'),
    'cbd_congestion_fee': ('cbd_congestion_fee', 'DOUBLE'),
}


# Cột được phép thiếu trong file nguồn: cbd_congestion_fee chỉ có từ 2025-01 (phí CBD bắt đầu 01/2025).
OPTIONAL_COLUMNS = {'cbd_congestion_fee': '2025-01'}  # cột -> tháng đầu tiên bắt buộc có


def to_bool(v, default=False):
    if v is None or str(v).strip() == '':
        return default
    return str(v).strip().lower() in ('1', 'true', 'yes', 'y')


def remote_metadata(file_name, timeout=30):
    """HEAD file trên TLC. Trả về dict (etag, content_length, last_modified) hoặc None nếu lỗi mạng."""
    req = urllib.request.Request(f'{BASE_URL}/{file_name}', method='HEAD',
                                 headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            length = resp.headers.get('Content-Length')
            return {'etag': (resp.headers.get('ETag') or '').strip('"') or None,
                    'content_length': int(length) if length else None,
                    'last_modified': resp.headers.get('Last-Modified')}
    except Exception as e:
        print(f'[SOURCE CHECK WARN] {file_name}: không lấy được metadata ({e})')
        return None


def save_metadata(con, file_name, meta, batch_id=None):
    if not meta:
        return
    con.execute('DELETE FROM control.source_file_meta WHERE source_file_name = ?', [file_name])
    con.execute('INSERT INTO control.source_file_meta (source_file_name, etag, content_length, '
                'last_modified, batch_id) VALUES (?, ?, ?, ?, ?)',
                [file_name, meta['etag'], meta['content_length'], meta['last_modified'], batch_id])


def source_changed(con, file_name):
    """(đã đổi?, lý do) cho một file đã nạp SUCCESS.

    Có bản ghi trong control.source_file_meta: so ETag (nếu cả hai có) hoặc kích thước.
    Chưa có (file nạp trước khi có bảng này): so kích thước file local với Content-Length;
    khớp thì ghi làm mốc, không nạp lại.
    """
    meta = remote_metadata(file_name)
    if meta is None:
        return False, 'không kiểm tra được nguồn'
    row = con.execute('SELECT etag, content_length FROM control.source_file_meta '
                      'WHERE source_file_name = ?', [file_name]).fetchone()
    if row:
        etag, length = row
        if etag and meta['etag']:
            if etag != meta['etag']:
                return True, f'ETag đổi {etag} -> {meta["etag"]}'
        elif length and meta['content_length'] and length != meta['content_length']:
            return True, f'kích thước đổi {length:,} -> {meta["content_length"]:,} byte'
        return False, 'nguồn không đổi'
    local = os.path.join(RAW_DIR, file_name)
    if os.path.exists(local) and meta['content_length'] and os.path.getsize(local) != meta['content_length']:
        return True, (f'file local {os.path.getsize(local):,} byte khác nguồn '
                      f'{meta["content_length"]:,} byte')
    save_metadata(con, file_name, meta)
    return False, 'ghi mốc phiên bản nguồn'


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


def build_insert_sql(con, path):
    """SELECT khớp cột theo tên (không phân biệt hoa thường).

    Thiếu cột bắt buộc thì lỗi: nếu nạp NULL, Fact sẽ COALESCE thành 0 (vd tiền boa = 0) mà không
    ai biết. Chỉ cột trong OPTIONAL_COLUMNS được thiếu ở các tháng trước tháng bắt buộc (thành NULL).
    """
    source_cols = {r[0].lower(): r[0] for r in
                   con.execute('SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet(?))',
                               [path]).fetchall()}
    match = re.search(r'(\d{4}-\d{2})\.parquet$', os.path.basename(path))
    file_month = match.group(1) if match else '9999-99'
    missing = [t for t, (src, _) in TARGET.items()
               if src.lower() not in source_cols
               and not (t in OPTIONAL_COLUMNS and file_month < OPTIONAL_COLUMNS[t])]
    if missing:
        raise ValueError(f'Schema drift: file thiếu cột bắt buộc {missing}; '
                         f'cột hiện có: {sorted(source_cols.values())}')
    extra = sorted(set(source_cols) - {src.lower() for src, _ in TARGET.values()})
    if extra:
        print(f'[SCHEMA WARN] {os.path.basename(path)}: cột mới chưa được nạp {extra}')
    select = []
    for target, (source, sql_type) in TARGET.items():
        actual = source_cols.get(source.lower())
        expr = f'CAST("{actual}" AS {sql_type})' if actual else f'CAST(NULL AS {sql_type})'
        select.append(f'{expr} AS {target}')
    cols = ', '.join(list(TARGET) + ['source_file_name', 'source_row_number', 'batch_id'])
    return (f'INSERT INTO {TABLE} ({cols}) '
            f'SELECT {", ".join(select)}, ? AS source_file_name, '
            f'file_row_number + 1 AS source_row_number, ? AS batch_id '
            f'FROM read_parquet(?, file_row_number = true)')


def load_one(con, file_name, cet=None, force_download=False):
    if not FILE_PATTERN.fullmatch(file_name):
        raise ValueError(f'Tên file không hợp lệ: {file_name!r} (yellow_tripdata_YYYY-MM.parquet)')
    started = datetime.now()
    cet = cet or started
    batch_id = next_batch_id(con)

    local = os.path.join(RAW_DIR, file_name)
    if force_download and os.path.exists(local):
        print(f'[DOWNLOAD] tải lại {file_name} (bỏ bản local)')
        os.remove(local)
    # Phiên bản nguồn chỉ biết chắc khi vừa tải; dùng lại file local cũ thì để source_changed() ghi mốc.
    meta = remote_metadata(file_name) if not os.path.exists(local) else None
    ok, reason = download_file_with_retry(file_name)
    if not ok:
        write_log(con, PIPELINE_NAME, batch_id, file_name, cet, None, 0, 'FAILED',
                  f'DOWNLOAD: {reason}', started)
        raise RuntimeError(f'{file_name}: {reason}')

    path = os.path.join(RAW_DIR, file_name)
    rows_read, loaded, status, err = None, 0, 'SUCCESS', None
    try:
        rows_read = con.execute('SELECT count(*) FROM read_parquet(?)', [path]).fetchone()[0]
        insert_sql = build_insert_sql(con, path)
        con.begin()
        con.execute(f'DELETE FROM {TABLE} WHERE source_file_name = ?', [file_name])
        loaded = con.execute(insert_sql, [file_name, batch_id, path]).fetchone()[0]
        con.commit()
    except Exception as e:
        status, err, loaded = 'FAILED', str(e)[:2000], 0
        try:
            con.rollback()
        except Exception:
            pass

    write_log(con, PIPELINE_NAME, batch_id, file_name, cet, rows_read, loaded, status, err, started)
    if status == 'SUCCESS':
        save_metadata(con, file_name, meta, batch_id)
    read_txt = f'{rows_read:,}' if rows_read is not None else '?'
    print(f'[{status}] {file_name} | đọc {read_txt} | nạp {loaded:,} | batch {batch_id} | {err or ""}')
    if status == 'FAILED':
        raise RuntimeError(err)


def get_lset_month(con):
    """LSET = tháng cuối của dãy tháng liên tục nạp thành công, tính từ FIRST_MONTH."""
    done = {r[0] for r in con.execute(
        'SELECT DISTINCT source_file_name FROM control.etl_control '
        "WHERE pipeline_name = ? AND status = 'SUCCESS' AND rows_read = rows_loaded",
        [PIPELINE_NAME]).fetchall()}
    y, m = map(int, FIRST_MONTH.split('-'))
    last = None
    while f'yellow_tripdata_{y}-{m:02d}.parquet' in done:
        last = f'{y}-{m:02d}'
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return last, done


@data_exporter
def load_trips_to_raw(*args, **kwargs):
    file_name = kwargs.get('file_name')
    year = kwargs.get('year')
    start_month = kwargs.get('start_month')
    end_month = kwargs.get('end_month')
    use_lset = to_bool(kwargs.get('use_lset'), False)
    check_updates = to_bool(kwargs.get('check_source_updates'), True)
    force_download = to_bool(kwargs.get('force_download'), False)
    cet = datetime.now()

    con = connect()
    try:
        init_schema(con)

        if file_name and file_name != 'ALL':
            load_one(con, file_name, cet=cet, force_download=force_download)
            return

        lset_month, done = get_lset_month(con)
        print(f'[ETL CONTROL] LSET (tháng dữ liệu liên tục cuối) = {lset_month} | CET = {cet}')

        months = [f'{y}-{m:02d}' for y in (2024, 2025) for m in range(1, 13)]
        if year:
            months = [m for m in months if m.startswith(str(year))]
        if use_lset and not (start_month or year) and lset_month:
            start_month = lset_month  # file cuối đã SUCCESS sẽ bị bỏ qua; tháng sau được nạp
        if start_month:
            months = [m for m in months if m >= str(start_month)]
        if end_month:
            months = [m for m in months if m <= str(end_month)]

        files = [f'yellow_tripdata_{m}.parquet' for m in months]
        print(f'Số file cần kiểm tra: {len(files)}')

        failed = []
        for f in files:
            reload_file = force_download
            if f in done and not force_download:
                changed, why = source_changed(con, f) if check_updates else (False, 'không kiểm tra')
                if not changed:
                    print(f'[SKIP] đã SUCCESS: {f} ({why})')
                    continue
                print(f'[SOURCE UPDATED] {f}: {why} -> tải lại và nạp lại')
                reload_file = True
            try:
                load_one(con, f, cet=cet, force_download=reload_file)
            except Exception as e:
                print(f'[FILE FAILED] {f}: {e}')
                failed.append(f)

        print(f'=== TỔNG KẾT: {len(files)} file | lỗi: {len(failed)} {failed}')
        if failed:
            raise RuntimeError(f'Còn {len(failed)} file chưa nạp được: {failed}')
    finally:
        con.close()

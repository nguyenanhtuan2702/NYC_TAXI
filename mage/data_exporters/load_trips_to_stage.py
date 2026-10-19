import io
import os
from datetime import datetime

import psycopg2
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

RAW_DIR = '/home/src/data/raw'
TABLE = 'stage.stg_yellow_taxi_trips'
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


@data_exporter
def load_trips_to_stage(*args, **kwargs):
    file_name = kwargs.get('file_name', 'yellow_tripdata_2024-01.parquet')
    batch_id = int(datetime.now().strftime('%Y%m%d%H%M%S'))
    started = datetime.now()
    pf = pq.ParquetFile(os.path.join(RAW_DIR, file_name))
    rows_read = pf.metadata.num_rows
    cols = ', '.join(TARGET + AUDIT)

    conn = psycopg2.connect(
        host=os.environ['POSTGRES_HOST'], port=os.environ['POSTGRES_PORT'],
        dbname=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'])
    cur = conn.cursor()
    loaded, status, err = 0, 'SUCCESS', None
    try:
        cur.execute(f'DELETE FROM {TABLE} WHERE source_file_name = %s', (file_name,))
        for batch in pf.iter_batches(batch_size=500_000):
            t = pa.Table.from_batches([batch])
            t = t.rename_columns([RENAME.get(c, c) for c in t.column_names])
            n = t.num_rows
            for c in TARGET:
                if c not in t.column_names:      # 2024 không có cbd_congestion_fee
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
        conn.commit()
    except Exception as e:
        conn.rollback()
        status, err, loaded = 'FAILED', str(e)[:2000], 0
    cur.execute(
        'INSERT INTO control.etl_control (pipeline_name, batch_id, source_file_name, '
        'rows_read, rows_loaded, rows_rejected, status, error_message, started_at) '
        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        ('ingest_trips_to_postgres', batch_id, file_name, rows_read, loaded,
         rows_read - loaded, status, err, started))
    conn.commit()
    conn.close()
    print(file_name, status, rows_read, loaded, err)
    if status == 'FAILED':
        raise RuntimeError(err)
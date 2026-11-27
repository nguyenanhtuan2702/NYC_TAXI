"""Ghi Taxi Zone Lookup vào DuckDB: raw.taxi_zone_lookup (thay toàn bộ mỗi lần chạy)."""
from datetime import datetime

try:
    from mage.utils.duckdb_helpers import connect, init_schema, next_batch_id, write_log
except ImportError:  # khi Mage đặt thư mục project làm gốc import
    from utils.duckdb_helpers import connect, init_schema, next_batch_id, write_log

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

PIPELINE_NAME = 'ingest_zone_lookup'
TABLE = 'raw.taxi_zone_lookup'
COLUMNS = ['location_id', 'borough', 'zone', 'service_zone', 'source_file_name', 'batch_id']


@data_exporter
def export_zone_lookup(df, **kwargs):
    started = datetime.now()
    file_name = df['source_file_name'].iloc[0]
    con = connect()
    try:
        init_schema(con)
        batch_id = next_batch_id(con)
        df = df.assign(batch_id=batch_id)[COLUMNS]
        rows_read, loaded, status, err = len(df), 0, 'SUCCESS', None
        try:
            con.register('zone_df', df)
            con.begin()
            con.execute(f'DELETE FROM {TABLE}')
            loaded = con.execute(
                f'INSERT INTO {TABLE} ({", ".join(COLUMNS)}) SELECT {", ".join(COLUMNS)} FROM zone_df'
            ).fetchone()[0]
            con.commit()
        except Exception as e:
            status, err, loaded = 'FAILED', str(e)[:2000], 0
            try:
                con.rollback()
            except Exception:
                pass
        finally:
            con.unregister('zone_df')

        write_log(con, PIPELINE_NAME, batch_id, file_name, started, rows_read, loaded,
                  status, err, started)
        print(f'[{status}] {file_name} | đọc {rows_read:,} | nạp {loaded:,} | batch {batch_id} | {err or ""}')
        if status == 'FAILED':
            raise RuntimeError(err)
    finally:
        con.close()

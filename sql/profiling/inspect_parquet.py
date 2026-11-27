import glob
import pyarrow.parquet as pq

files = sorted(glob.glob('/home/src/data/raw/*.parquet'))
base = None
for f in files:
    name = f.split('/')[-1]
    schema = pq.read_schema(f)
    cols = [(n, str(t)) for n, t in zip(schema.names, schema.types)]
    rows = pq.ParquetFile(f).metadata.num_rows
    if base is None:
        base = cols
        print(f'{name}: {rows} dong')
        for c in cols:
            print('   ', c)
    elif cols != base:
        print(f'{name}: {rows} dong, KHAC file dau:', sorted(set(cols) ^ set(base)))
    else:
        print(f'{name}: {rows} dong, giong file dau')
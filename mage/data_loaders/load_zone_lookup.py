import pandas as pd

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader


@data_loader
def load_zone_lookup(*args, **kwargs):
    path = '/home/src/data/reference/taxi_zone_lookup.csv'
    # keep_default_na=False: giữ nguyên chữ 'N/A' trong file nguồn, không biến thành NULL
    df = pd.read_csv(path, keep_default_na=False)
    df = df.rename(columns={
        'LocationID': 'location_id',
        'Borough': 'borough',
        'Zone': 'zone',
    })
    df['source_file_name'] = 'taxi_zone_lookup.csv'
    df['batch_id'] = int(pd.Timestamp.now().strftime('%Y%m%d%H%M%S'))
    return df
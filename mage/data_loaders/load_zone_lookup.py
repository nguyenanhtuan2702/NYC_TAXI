import pandas as pd

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader

SOURCE_FILE = 'taxi_zone_lookup.csv'


@data_loader
def load_zone_lookup(*args, **kwargs):
    path = f'/home/src/data/reference/{SOURCE_FILE}'
    # keep_default_na=False: giữ nguyên chữ 'N/A' trong file nguồn, không biến thành NULL
    df = pd.read_csv(path, keep_default_na=False)
    df = df.rename(columns={
        'LocationID': 'location_id',
        'Borough': 'borough',
        'Zone': 'zone',
    })
    df['source_file_name'] = SOURCE_FILE
    return df

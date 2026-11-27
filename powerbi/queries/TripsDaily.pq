// Mart: ngày đón × khu vực đón × hãng × thanh toán × mã giá (A1, A2, A3, A6, A8, B2, B3)
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\mart_trips_daily.parquet"))
in
    Source

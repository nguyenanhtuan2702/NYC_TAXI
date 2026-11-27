// Taxi Zone, SCD Type 2: mỗi phiên bản một dòng (locationsk = locationid*100 + versionno)
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\dimlocation.parquet")),
    // Gắn tọa độ tâm khu vực (cho visual Map/Azure Maps dạng bong bóng). Mã 264, 265 không có tọa độ.
    Centroids = Csv.Document(File.Contents(RepoFolder & "\powerbi\map_shapes\taxi_zone_centroids.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    CentroidsHeader = Table.PromoteHeaders(Centroids, [PromoteAllScalars = true]),
    CentroidsTyped = Table.TransformColumnTypes(CentroidsHeader,
        {{"LocationID", Int64.Type}, {"latitude", type number}, {"longitude", type number}}, "en-US"),
    Merged = Table.NestedJoin(Source, {"locationid"}, CentroidsTyped, {"LocationID"}, "c", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(Merged, "c", {"latitude", "longitude"})
in
    Expanded

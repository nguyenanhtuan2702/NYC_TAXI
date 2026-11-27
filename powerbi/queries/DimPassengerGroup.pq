// Nhóm hành khách
// passengerorder: thứ tự hiển thị (1 passenger, 2-4, 5+, rồi No passenger count và Unknown cuối cùng);
// dùng làm "Sort by column" của passengergroupname để nhóm thiếu dữ liệu không đứng đầu bảng.
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\dimpassengergroup.parquet")),
    WithOrder = Table.AddColumn(
        Source,
        "passengerorder",
        each if [passengergroupsk] > 0 then [passengergroupsk] else 9 - [passengergroupsk],
        Int64.Type
    )
in
    WithOrder

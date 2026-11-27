// Bảng tĩnh các khoản doanh thu cho waterfall trang 7 (B3). Không tạo quan hệ: measure
// `Component Amount` đọc tên khoản bằng SELECTEDVALUE. Sort by column: component theo componentorder.
let
    Source = #table(
        type table [component = text, componentorder = Int64.Type],
        {
            {"Fare", 1},
            {"Tip", 2},
            {"Tolls", 3},
            {"Congestion surcharge", 4},
            {"Airport fee", 5},
            {"CBD congestion fee", 6},
            {"Other surcharges", 7},
            {"Unreconciled", 8}
        }
    )
in
    Source

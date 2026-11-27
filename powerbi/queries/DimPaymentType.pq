// Hình thức thanh toán
// paymentorder: thứ tự hiển thị cố định (Credit card, Cash, Dispute, No charge, Unknown cuối cùng) cho
// legend và thanh chồng 100%. Dùng làm "Sort by column" của paymenttypename (Unknown ứng với nhiều mã
// -1, 0, 5 nên không sắp theo paymenttypeid được).
let
    Source = Parquet.Document(File.Contents(RepoFolder & "\data\bi\dimpaymenttype.parquet")),
    WithOrder = Table.AddColumn(
        Source,
        "paymentorder",
        each
            if [paymenttypename] = "Credit card" then 1
            else if [paymenttypename] = "Cash" then 2
            else if [paymenttypename] = "Dispute" then 3
            else if [paymenttypename] = "No charge" then 4
            else 9,
        Int64.Type
    )
in
    WithOrder

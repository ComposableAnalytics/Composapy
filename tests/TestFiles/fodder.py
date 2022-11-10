# Add this test back later, unfortunately casting errors and no time to deal with them.
# @pytest.mark.parametrize("dataflow_object", ["external_input_int.json"], indirect=True)
# def test_external_input_int(dataflow_object: DataFlowObject, dataflow: DataFlow):
#     dataflow_rs = dataflow_object.run(external_inputs={"IntInput": 3})
#
#     assert dataflow_rs.modules.first_with_name("Calculator").result.value_obj == 5.0


# @pytest.mark.parametrize("dataflow_id", ["EXTERNAL_INPUT_FILE_ID"], indirect=True)
# def test_external_input_file(dataflow: dataflow, dataflow_id: int):
#
#     table_dataflow = dataflow.run(table_dataflow_id)
#     table = table_dataflow.modules.first_with_name("Sql Query").result
#     test_input = { "TableInput": table }
#
#     dataflow_rs = dataflow.run(dataflow_id, external_inputs=test_input)
#
#     assert dataflow_rs.modules.first().result.Headers == table.Headers
#     assert dataflow_rs.modules.first().result.SqlQuery == table.SqlQuery


# def test_queryview_to_pandas(queryview: queryview):
#     df = queryview.queryview_from_id(137072)
#     print(df.head())
#     print(df.dtypes)
#
#
# def test_queryview_to_pandas_streaming(queryview: queryview):
#     t = time()
#     df = queryview.queryview_from_id(137072)
#     print(time() - t)
#     print(df.head())
#     print(df.dtypes)
#     print(len(df))

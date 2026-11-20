"""The list members a script can reach on Table.Headers and Table.Columns, which were .NET collections."""

from composapy.dataflow.api import DataFlow

run = DataFlow.create(file_path=fixture("tablecreator.json")).run()
table = run.modules.first_with_name("Table Creator").result.value
headers = table.Headers
columns = table.Columns

record("headers.initial", list(headers))
# reading
attempt("headers.Count", lambda: headers.Count)
attempt("headers.Count_type", lambda: type(headers.Count).__name__)
attempt("headers.len", lambda: len(headers))
attempt("headers.index_0", lambda: headers[0])
attempt("headers.index_last", lambda: headers[1])
attempt("headers.index_negative", lambda: headers[-1])
attempt("headers.index_out_of_range", lambda: headers[5])
attempt("headers.index_not_an_int", lambda: headers["a"])
attempt("headers.slice", lambda: list(headers[0:1]))
attempt("headers.in_operator", lambda: ("a" in headers, "zz" in headers))
attempt("headers.iteration", lambda: [h for h in headers])
attempt("headers.Contains", lambda: (headers.Contains("a"), headers.Contains("zz")))
attempt("headers.Contains_wrong_type", lambda: headers.Contains(5))
attempt("headers.IndexOf", lambda: (headers.IndexOf("b"), headers.IndexOf("zz")))
attempt("headers.LastIndexOf", lambda: headers.LastIndexOf("a"))
attempt("headers.ToArray", lambda: list(headers.ToArray()))
attempt("headers.GetRange", lambda: list(headers.GetRange(0, 1)))
attempt("headers.equals_a_list", lambda: headers == ["a", "b"])
attempt("headers.not_equals_a_list", lambda: headers != ["a", "b"])
attempt("headers.bool", lambda: bool(headers))
attempt("headers.sorted", lambda: sorted(headers))
attempt("headers.reversed", lambda: list(reversed(list(headers))))
attempt("headers.join", lambda: ", ".join(headers))
attempt("headers.has_append", lambda: hasattr(headers, "append"))
attempt("headers.has_Add", lambda: hasattr(headers, "Add"))
attempt("headers.python_index_method", lambda: headers.index("b"))
attempt("headers.python_count_method", lambda: headers.count("a"))

# columns
attempt("columns.Count", lambda: columns.Count)
attempt("columns.len", lambda: len(columns))
attempt("columns.by_position", lambda: (columns[0].Name, columns[1].Name))
attempt("columns.by_name", lambda: columns["b"].Type)
attempt("columns.names", lambda: [c.Name for c in columns])
attempt("columns.Indexes_Keys", lambda: list(columns.Indexes.Keys))
attempt("columns.missing_name", lambda: columns["zz"])
attempt("columns.Contains_name", lambda: columns.Contains("a"))
attempt("columns.has_Add", lambda: hasattr(columns, "Add"))

# mutating, in a fixed order so each result depends only on the ones before it
attempt("headers.Add", lambda: (headers.Add("c"), list(headers))[1])
attempt("headers.Insert", lambda: (headers.Insert(0, "z"), list(headers))[1])
attempt("headers.Insert_out_of_range", lambda: headers.Insert(99, "q"))
attempt("headers.Remove", lambda: (headers.Remove("z"), list(headers)))
attempt("headers.Remove_missing", lambda: headers.Remove("zz"))
attempt("headers.RemoveAt", lambda: (headers.RemoveAt(0), list(headers))[1])
attempt("headers.RemoveAt_out_of_range", lambda: headers.RemoveAt(99))
attempt("headers.assign_index", lambda: (headers.__setitem__(0, "A"), list(headers))[1])
attempt("headers.Reverse", lambda: (headers.Reverse(), list(headers))[1])
attempt("headers.Sort", lambda: (headers.Sort(), list(headers))[1])
attempt("headers.Clear", lambda: (headers.Clear(), headers.Count, list(headers)))
attempt("headers.Count_after_clear", lambda: headers.Count)

# last, because the candidate accepts both and the baseline refuses both: every result after them would differ in a different way
attempt("headers.Add_wrong_type", lambda: headers.Add(5))
attempt("headers.AddRange", lambda: (headers.AddRange(["d", "e"]), list(headers))[1])

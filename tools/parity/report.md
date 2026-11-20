# Parity report: composapy 0.13.3 and the release candidate

Both variants ran 66 scripts against one local instance and a token session, 943 records each. 832 records are identical; 111 differ, and every difference is classified: 4 fixed, 105 intentional, 2 visual. **0 are open.**

## What was compared

- Baseline: composapy 0.13.3 with pythonnet 3.0.1 (the wheel DataLabs run today)
- Candidate: composapy 1.0.0.dev6, with no pythonnet
- Packages: numpy 1.25.0, pandas 2.0.3, requests 2.28.1 (the DataLab Python 3.11 pins) in both
- Instance: a local platform instance, reached over a token session; saved Keys and QueryViews are created before the run and removed after

Each script runs in its own process under each variant. A record is a value a caller can observe (`record`), or the result of a call that may fail (`attempt`: its value, or the class name and message of the exception). Records are compared as canonical JSON text, so an int and a float, or a bool and an int, are different. DataFrames compare by columns, dtypes, index, and every cell. The wrapper cases run `nb_wrap` and `script_wrap` as DataLab does and compare the exit code, `outputs.serialized` (value, key order, member order), and the tables behind any returned Table.

## Records by area

| Area | Scripts | Records | Differences |
|---|---|---|---|
| dataflow | 5 | 141 | 28 |
| dataframe | 1 | 37 | 3 |
| errors | 1 | 9 | 4 |
| file_reference | 1 | 8 | 1 |
| key | 3 | 42 | 1 |
| net_list | 1 | 51 | 13 |
| queryview | 5 | 103 | 5 |
| session | 1 | 37 | 6 |
| other | 1 | 24 | 0 |
| table | 1 | 8 | 0 |
| to_table | 1 | 18 | 1 |
| uri | 1 | 102 | 18 |
| notebooks | 11 | 87 | 0 |
| notebook DataFrames | 16 | 138 | 0 |
| scripts | 17 | 138 | 31 |

## Fixed: a bug in the baseline that the candidate does not have

- DataFlow.run_status raised TypeError in the baseline ("array index has type ExecutionStatus, expected an integer"), so the operation never worked in the 0.13.3 build DataLabs run today. The candidate returns the status name.
  - 1 difference: `dataflow_api / run_status`
- DataFlow.wait_for_run_execution raised the same TypeError in the baseline, so it never returned; the candidate returns the status name and run id.
  - 1 difference: `dataflow_api / wait_for_run_execution`
- The baseline's message was the literal text "'{name}'" because the original string lacked its f prefix; the candidate names the input.
  - 1 difference: `queryview_run_by_id / inputs_name_does_not_exist`
- resource_manager.AvailableServices() raised SystemError ("error return without exception set") in the baseline; the candidate returns the 41 service names.
  - 1 difference: `session_members / resource_manager.AvailableServices`

## Intentional: a change recorded with its reason

- pythonnet refused an argument of the wrong type with TypeError before any request; the candidate has no overloads to resolve, so the server refuses it and ServiceFault carries the server's message (Decision Log, 2026-10-27).
  - 1 difference: `dataflow_api / get_not_an_id`
- A file path that does not exist: System.IO.DirectoryNotFoundException becomes Python's FileNotFoundError (Exceptions, R5).
  - 1 difference: `dataflow_files / input_path_does_not_exist`
- A directory given as a file input: System.UnauthorizedAccessException becomes Python's PermissionError (Exceptions, R5).
  - 1 difference: `dataflow_files / input_is_a_directory`
- A relative folder for to_file is refused by both, as it always was: the baseline raised System.ArgumentException and the candidate raises ValueError, with the same message. (Callers pass an absolute folder, or none, which is the current directory.)
  - 1 difference: `dataflow_files / to_file_into_a_relative_folder`
- Both variants refuse the value. The baseline refused it on the client, in pythonnet's conversion to .NET or in a .NET cast, with System.OverflowError or System.InvalidCastException; the candidate sends it and the server's deserializer refuses it, so ServiceFault carries the server's message (Decision Log, 2026-10-27).
  - 8 differences: `dataflow_inputs / IntInput.int_over32`, `dataflow_inputs / IntInput.int_big`, `dataflow_inputs / IntInput.int_huge`, `dataflow_inputs / IntInput.float_fraction`, `dataflow_inputs / IntInput.bool_true`, `dataflow_inputs / IntInput.text_words`, `dataflow_inputs / IntInput.list`, `dataflow_inputs / IntInput.dict`
- The candidate accepts a value the baseline refused: the server's JSON deserializer reads 5.0, written as 5, as an Int32. Nothing that worked before changes.
  - 1 difference: `dataflow_inputs / IntInput.float_whole`
- The candidate accepts a value the baseline refused: the server's JSON deserializer reads the text "7" as an Int32. Nothing that worked before changes.
  - 1 difference: `dataflow_inputs / IntInput.text_number`
- Both variants refuse the value. The baseline refused it on the client, in pythonnet's conversion to .NET or in a .NET cast, with System.OverflowError or System.InvalidCastException; the candidate sends it and the server's deserializer refuses it, so ServiceFault carries the server's message (Decision Log, 2026-10-27). The dataflow has no default for its Int input, so the run fails in both.
  - 2 differences: `dataflow_inputs / input_name_does_not_exist`, `dataflow_inputs / run_with_no_inputs`
- The server's message is the same; the baseline raised System.ServiceModel.FaultException[FaultDetail] with the .NET stack trace appended and the candidate raises composapy.exceptions.ServiceFault with the server's message (Exceptions, R5).
  - 12 differences: `dataflow_inputs / ColumnType.ascii`, `dataflow_inputs / ColumnType.quote`, `dataflow_inputs / ColumnType.unicode`, `dataflow_inputs / ColumnType.empty`, `dataflow_inputs / ColumnType.long`, `dataflow_tables / table_module_input.module_results`, `dataflow_tables / table_output_to_input.module_results`, `dataflow_tables / convert_table_to_pandas_dtypes.module_results`, `dataflow_tables / empty.module_results`, `key_search / syntax_error`, `queryview_run_by_id / run_missing_id`, `to_table_direct / handle_is_not_a_handle`
- inf, -inf, and nan cannot be written in JSON. The baseline stored 0.0 in every one of those cells, silently; the candidate stores a missing value (NaN). Neither returns what was sent; the migration page says so.
  - 1 difference: `dataframe_inputs / float_special`
- A list for a table input is refused by both: InvalidCastException in the baseline, TypeError from the candidate before any request.
  - 1 difference: `dataframe_inputs / not_a_dataframe`
- A Series for a table input is refused by both: InvalidCastException in the baseline, TypeError from the candidate's encoder.
  - 1 difference: `dataframe_inputs / series`
- A file that does not exist raised System.IO.DirectoryNotFoundException with a .NET stack trace; it now raises Python's FileNotFoundError. Same resolution as the faults: a .NET exception type cannot exist without the CLR.
  - 1 difference: `errors / dataflow_create_missing_file`
- Same server message. The baseline raised System.ServiceModel.FaultException[FaultDetail] with the .NET stack trace appended; the candidate raises composapy.exceptions.ServiceFault with the server's message (Exceptions, R5's resolution for error types that cannot exist without the CLR).
  - 1 difference: `errors / key_get_missing_name`
- Same server message; FaultException[FaultDetail] becomes ServiceFault (Exceptions, R5).
  - 2 differences: `errors / key_search_no_match`, `errors / queryview_run_missing_id`
- Python's own behavior is kept where the .NET wrapper refused: a negative index counts from the end; List<T> raised ArgumentOutOfRangeException.
  - 1 difference: `net_list_members / headers.index_negative`
- An index past the end: ArgumentOutOfRangeException becomes IndexError (Exceptions, R5).
  - 1 difference: `net_list_members / headers.index_out_of_range`
- A non-integer index: both raise TypeError, with Python's message in place of pythonnet's.
  - 1 difference: `net_list_members / headers.index_not_an_int`
- Python's own behavior is kept where the .NET wrapper refused: slicing works; the .NET wrapper raised TypeError.
  - 1 difference: `net_list_members / headers.slice`
- Python's own behavior is kept where the .NET wrapper refused: Contains(5) on a list of strings is False; the .NET wrapper raised TypeError for the wrong element type.
  - 1 difference: `net_list_members / headers.Contains_wrong_type`
- Python's own behavior is kept where the .NET wrapper refused: a NetList equals a list with the same items; the .NET wrapper never equaled one (False).
  - 1 difference: `net_list_members / headers.equals_a_list`
- Python's own behavior is kept where the .NET wrapper refused: the same difference as equals_a_list.
  - 1 difference: `net_list_members / headers.not_equals_a_list`
- Python's own behavior is kept where the .NET wrapper refused: a column can be read by position as well as by name; the .NET KeyedCollection raised TypeError for an int.
  - 1 difference: `net_list_members / columns.by_position`
- A column name that does not exist: KeyNotFoundException becomes KeyError (Exceptions, R5).
  - 1 difference: `net_list_members / columns.missing_name`
- An insert index past the end: ArgumentOutOfRangeException becomes IndexError, with the same message (Exceptions, R5).
  - 1 difference: `net_list_members / headers.Insert_out_of_range`
- RemoveAt with an index outside the list: ArgumentOutOfRangeException becomes IndexError, with the same message (Exceptions, R5).
  - 1 difference: `net_list_members / headers.RemoveAt_out_of_range`
- Python's own behavior is kept where the .NET wrapper refused: Add(5) to a list of strings is accepted, because a Python list has no element type; the .NET wrapper raised TypeError.
  - 1 difference: `net_list_members / headers.Add_wrong_type`
- Python's own behavior is kept where the .NET wrapper refused: AddRange takes a Python list, which the .NET wrapper refused with TypeError; any iterable is accepted.
  - 1 difference: `net_list_members / headers.AddRange`
- A timeout above the Int32 range raised OverflowError in the baseline's Int32 property. The candidate stores it and the server refuses it when a query runs (Decision Log, 2026-10-27).
  - 1 difference: `queryview_driver_members / set_timeout.huge`
- Both raise TypeError. The message was pythonnet's "'int' value cannot be converted to System.String" and is now composapy's own.
  - 1 difference: `queryview_errors / query_not_text`
- An argument of the wrong type was refused by pythonnet's overload resolution with TypeError before any request. The candidate has no overloads to resolve, so the server refuses it and ServiceFault carries the server's message (Decision Log, 2026-10-27).
  - 1 difference: `queryview_run_by_id / run_not_an_id`
- Session.close() is new: the candidate holds an HTTP session that has to be closed, and the baseline Session had no such method. Nothing that worked changes.
  - 1 difference: `session_members / close`
- A string for auth_mode failed in the baseline with an incidental AttributeError (the Session was left without a ResourceManager). The candidate refuses it up front with TypeError and a message that names the problem.
  - 1 difference: `session_members / auth_mode_not_an_enum`
- The baseline raised the .NET System.ServiceModel.Security.MessageSecurityException wrapping a WebException (401); the candidate raises composapy.exceptions.AuthenticationError with the server's message. Both fail on the first call (Exceptions, R5).
  - 2 differences: `session_members / invalid_token_first_call`, `session_members / invalid_token_through_the_api`
- The baseline raised the .NET System.ServiceModel.Security.MessageSecurityException wrapping a WebException (401); the candidate raises composapy.exceptions.AuthenticationError with the server's message. Both fail on the first call (Exceptions, R5). The candidate's message says the login page issued no .ASPXAUTH cookie.
  - 1 difference: `session_members / form_wrong_password_first_call`
- FileReference.Uri is a str subclass (composapy.contracts.uri.Uri) with the System.Uri members scripts use, and every member of an absolute URI returns what System.Uri returned. A System.Uri raised TypeError when compared with a string and the candidate's compares equal to its text; a relative URI raises RelativeUriError where System.Uri raised InvalidOperationException, with the same message (Decision Log, 2026-10-27).
  - 18 differences: `uri_members / windows_file.equals_text`, `uri_members / windows_file_escaped.equals_text`, `uri_members / unc_file.equals_text`, `uri_members / https_full.equals_text`, `uri_members / http_default_port.equals_text`, `uri_members / site_relative.AbsoluteUri`, `uri_members / site_relative.AbsolutePath`, `uri_members / site_relative.LocalPath`, `uri_members / site_relative.Scheme`, `uri_members / site_relative.Host`, `uri_members / site_relative.Port`, `uri_members / site_relative.IsFile`, and 6 more
- The baseline could not return an int above the Int32 range: System.Int32(x) raised OverflowError in serialize_return_values. The candidate writes it as an Int64 (Decision Log, 2026-10-27).
  - 16 differences: `wrapper_script_big_ints / exit_code`, `wrapper_script_big_ints / outputs_file_written`, `wrapper_script_big_ints / outputs_file_has_bom`, `wrapper_script_big_ints / outputs_file_is_compact_json`, `wrapper_script_big_ints / output_keys`, `wrapper_script_big_ints / entry_member_order`, `wrapper_script_big_ints / output.output1`, `wrapper_script_big_ints / output.output2`, `wrapper_script_return_big_int / exit_code`, `wrapper_script_return_big_int / outputs_file_written`, `wrapper_script_return_big_int / outputs_file_has_bom`, `wrapper_script_return_big_int / outputs_file_is_compact_json`, and 4 more
- The .NET deserializer reads a float parameter as System.Decimal, which the baseline's own serialize_return_values refused with TypeNotSupportedError, so a script could not hand a float parameter back. The candidate's parameter is a float and is returned (Risks: a float arrives as Decimal).
  - 8 differences: `wrapper_script_floats / exit_code`, `wrapper_script_floats / outputs_file_written`, `wrapper_script_floats / outputs_file_has_bom`, `wrapper_script_floats / outputs_file_is_compact_json`, `wrapper_script_floats / output_keys`, `wrapper_script_floats / entry_member_order`, `wrapper_script_floats / output.output1`, `wrapper_script_floats / output.output2`
- Under the baseline a function defined in a script could not see the script's own imports: exec(code, globals, locals) raised NameError. The candidate runs the script in one namespace (Execution wrappers).
  - 7 differences: `wrapper_script_single_namespace / exit_code`, `wrapper_script_single_namespace / outputs_file_written`, `wrapper_script_single_namespace / outputs_file_has_bom`, `wrapper_script_single_namespace / outputs_file_is_compact_json`, `wrapper_script_single_namespace / output_keys`, `wrapper_script_single_namespace / entry_member_order`, `wrapper_script_single_namespace / output.area`

## Visual only (R5)

- Table.Headers was a .NET List[String] and is a NetList, a list with the List<T> members a script could call (Count, Contains, IndexOf, LastIndexOf, ToArray, GetRange, Add, AddRange, Insert, Remove, RemoveAt, Reverse, Sort, Clear). The type name differs; net_list_members compares every member against the baseline (Decision Log, 2026-10-27).
  - 1 difference: `dataflow_tables / tablecreator.headers_type`
- str(file_reference) was the .NET type name, CompAnalytics.Contracts.FileReference; it is now the contract's text. Nothing reads it.
  - 1 difference: `file_reference / str`

## Import time

| Python | Baseline median | Candidate median | Faster | Forbidden imports |
|---|---|---|---|---|
| py38 (3.8.10) | 28.957 s | 0.595 s | 49x | none |
| py311 (3.11.4) | 27.939 s | 0.653 s | 43x | none |
| py313 (3.13.11) | 31.578 s | 0.706 s | 45x | none |

Measured with composapy 1.0.0.dev6 

## Public names

100 baseline names are .NET types and are not required. Of the 79 other names the candidate lacks, 16 are private, 45 are incidental imports (`os`, `np`, `json`, and the like that leaked into a module namespace), and 18 were defined by composapy: the removed .NET plumbing (`bindings`, `stream`, `configure_binding`, `add_dll_reference`) and internals of the old `patch` modules (the papermill translators, now in `notebook/translators.py`, and `deep_copy` and `reduce_ex`). No type of a name that remains changed. Nothing in the product source uses any of them.

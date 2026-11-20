"""to_table called directly with an execution handle, for the frames a notebook or a script would pass."""

import numpy as np
import pandas as pd

from composapy import to_table
from composapy.dataflow.api import DataFlow
from composapy.session import get_session

try:  # where ExecutionContextOptions lives differs; both variants have it
    from composapy.contracts import ExecutionContextOptions
except ImportError:
    from CompAnalytics.Contracts import ExecutionContextOptions

flow = DataFlow.create(file_path=fixture("calculator_test.json"))
handle = get_session().app_service.CreateExecutionContext(
    flow.contract, ExecutionContextOptions()
)


def made(df):
    table = to_table(df, handle)
    return {
        "columns": [(c.Name, c.Type) for c in table.Columns],
        "headers": list(table.Headers),
        "df": table.to_pandas(),
    }


CASES = {
    "ints": "pd.DataFrame({'a': [1, 2, 3]})",
    "mixed": "pd.DataFrame({'i': [1, 2], 'f': [1.5, 2.5], 's': ['x', None], 'b': [True, False]})",
    "nullable": "pd.DataFrame({'n': pd.array([1, None], dtype='Int64'), 'b': pd.array([True, None], dtype='boolean')})",
    "datetimes": "pd.DataFrame({'d': pd.to_datetime(['2021-10-01 12:34:56', '2021-10-02 00:00:00'])})",
    "aware_datetimes": "pd.DataFrame({'d': pd.to_datetime(['2021-10-01 12:34:56']).tz_localize('UTC')})",
    "int_sizes": "pd.DataFrame({'i8': np.array([1], dtype='int8'), 'u16': np.array([1], dtype='uint16'), 'i64': np.array([1], dtype='int64')})",
    "floats": "pd.DataFrame({'f32': np.array([1.5], dtype='float32'), 'f64': [2.5]})",
    "names": "pd.DataFrame({'a b': [1], 'select': [2], '1x': [3]})",
    "named_index": "pd.DataFrame({'a': [1, 2]}, index=pd.Index([10, 20], name='key'))",
    "multiindex_columns": "pd.DataFrame([[1, 2]], columns=pd.MultiIndex.from_tuples([('a', 'x'), ('a', 'y')]))",
    "unicode": "pd.DataFrame({'s': ['caf\\u00e9', '\\u4e2d\\u6587']})",
    "empty_with_columns": "pd.DataFrame({'a': pd.Series([], dtype='int64')})",
    "no_columns": "pd.DataFrame()",
    "duplicate_names": "pd.DataFrame([[1, 2]], columns=['a', 'a'])",
}
for label, expression in CASES.items():
    attempt(label, lambda e=expression: made(eval(e)))

attempt("not_a_frame", lambda: to_table([1, 2], handle))
attempt("none", lambda: to_table(None, handle))
attempt("handle_is_not_a_handle", lambda: to_table(pd.DataFrame({"a": [1]}), "handle"))
attempt(
    "without_a_session",
    lambda: (
        __import__(
            "composapy.session", fromlist=["Session"]
        ).Session.clear_registration(),
        to_table(pd.DataFrame({"a": [1]}), handle),
    )[1],
)

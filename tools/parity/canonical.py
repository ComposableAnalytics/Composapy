"""Reduce any value a corpus script records to plain JSON, so the baseline's and the candidate's results compare as text.

The baseline returns .NET objects and the candidate returns Python ones, so only what a caller can observe is kept: the
values, a DataFrame's columns, dtypes, and cells, and the exact text of json.dumps. Anything this module does not know
becomes {"$repr": ..., "$type": ...}, which a comparison reports as a difference to classify and never silently equates.
"""

import base64
import datetime
import decimal
import math


def _na_marker(value):
    """'NA', 'NaT', or 'nan' for the missing-value singletons, else None. pandas is imported only if it is already loaded."""
    import sys

    pd = sys.modules.get("pandas")
    if pd is not None:
        if value is pd.NA:
            return "NA"
        if value is pd.NaT:
            return "NaT"
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    return None


def canonicalize(value):
    import sys

    marker = _na_marker(value)
    if marker is not None:
        return {"$na": marker}
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return {"$float": repr(value)} if math.isinf(value) else value
    if isinstance(value, decimal.Decimal):
        return {"$decimal": str(value)}
    if isinstance(value, (bytes, bytearray)):
        return {"$bytes": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, datetime.datetime):
        return {
            "$datetime": value.isoformat(),
            "$tz": str(value.tzinfo) if value.tzinfo else None,
        }
    if isinstance(value, datetime.date):
        return {"$date": value.isoformat()}
    if isinstance(value, datetime.time):
        return {"$time": value.isoformat()}
    if isinstance(value, datetime.timedelta):
        return {"$timedelta_seconds": value.total_seconds()}

    np = sys.modules.get("numpy")
    if np is not None and isinstance(value, np.generic):
        return canonicalize(value.item())
    pd = sys.modules.get("pandas")
    if pd is not None:
        if isinstance(value, pd.DataFrame):
            return {
                "$dataframe": {
                    "columns": [str(c) for c in value.columns],
                    "dtypes": {str(c): str(t) for c, t in value.dtypes.items()},
                    "index": [canonicalize(i) for i in value.index],
                    "values": [
                        [canonicalize(cell) for cell in row]
                        for row in value.itertuples(index=False, name=None)
                    ],
                }
            }
        if isinstance(value, pd.Series):
            return {
                "$series": {
                    "name": canonicalize(value.name),
                    "dtype": str(value.dtype),
                    "index": [canonicalize(i) for i in value.index],
                    "values": [canonicalize(v) for v in value],
                }
            }
        if isinstance(value, pd.Timestamp):
            return {
                "$datetime": value.isoformat(),
                "$tz": str(value.tzinfo) if value.tzinfo else None,
            }

    if isinstance(value, tuple):
        return {"$tuple": [canonicalize(v) for v in value]}
    if isinstance(value, (list, set, frozenset)):
        items = [canonicalize(v) for v in value]
        return items if isinstance(value, list) else {"$set": sorted(items, key=repr)}
    if isinstance(value, dict):
        return {str(k): canonicalize(v) for k, v in value.items()}
    return {"$repr": repr(value), "$type": type(value).__name__}

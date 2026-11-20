import json
import re
from datetime import datetime, timedelta, timezone

from .objects import KeyedList, NetList, class_for

_DATE = re.compile(r"^/Date\((-?\d+)([+-]\d{4})?\)/$")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_KEYED = ("ModuleInputs", "ModuleOutputs")


def unwrap(value):
    return value["d"]


def parse_fault(value):
    """Message, ExceptionType, and StackTrace from any error body. Read them with .get
    because a 401 body has no __type and may have no ExceptionDetail."""
    return {
        "Message": value.get("Message"),
        "ExceptionType": value.get("ExceptionType"),
        "StackTrace": value.get("StackTrace"),
    }


def decode(text):
    try:
        value = json.loads(text, object_pairs_hook=_make_object)
    except json.JSONDecodeError:
        # The .NET serializer writes an infinite double as INF or -INF, which json can't read
        spelled = _INF.sub(_spell_infinity, text)
        if spelled == text:
            raise
        value = json.loads(spelled, object_pairs_hook=_make_object)
    return _convert(value)


# A string is matched whole and left alone, so an INF inside text stays text
_INF = re.compile(r'"(?:\\.|[^"\\])*"|(-?)\bINF\b')


def _spell_infinity(match):
    if match.group(0).startswith('"'):
        return match.group(0)
    return f"{match.group(1)}Infinity"


def _make_object(pairs):
    pairs = [
        (k, KeyedList(v) if k in _KEYED and isinstance(v, list) else _convert(v))
        for k, v in pairs
    ]
    type_name = pairs[0][1] if pairs and pairs[0][0] == "__type" else None
    return class_for(type_name)(pairs)


def _convert(v):
    if isinstance(v, str):
        m = _DATE.match(v)
        return _to_datetime(m) if m else v
    if isinstance(v, list):
        return NetList([_convert(x) for x in v])
    return v


def _to_datetime(m):
    utc = _EPOCH + timedelta(milliseconds=int(m.group(1)))
    offset = m.group(2)
    if offset is None:
        return utc
    sign = 1 if offset[0] == "+" else -1
    delta = sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
    return utc.astimezone(timezone(delta, offset))


def encode(obj, compact=False):
    """JSON text for a contract object. compact=True writes no space after a colon or comma, as the .NET serializer does."""
    if compact:
        return json.dumps(obj, default=_encode_other, separators=(",", ":"))
    return json.dumps(obj, default=_encode_other)


def _encode_other(o):
    if isinstance(o, datetime):
        return _from_datetime(o)
    raise TypeError(f"Cannot encode {type(o).__name__}")


def _from_datetime(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ms = (dt - _EPOCH) // timedelta(milliseconds=1)
    if dt.tzinfo is timezone.utc:
        return f"/Date({ms})/"
    minutes = int(dt.utcoffset().total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"/Date({ms}{sign}{abs(minutes) // 60:02d}{abs(minutes) % 60:02d})/"

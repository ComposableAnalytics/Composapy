"""Offline tests for tools/parity: canonical values, and comparing and classifying result files."""

import datetime
import decimal
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tools.parity.canonical import canonicalize  # noqa: E402
from tools.parity.compare_results import (
    classify,
    compare,
    compare_script,
    open_differences,
    load,
)  # noqa: E402

# ----------------------------------------------------------------------------------------------
# canonicalize
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value", [None, True, False, 0, -3, 2**40, "text", "", 1.5, -0.25]
)
def test_plain_values_stay_as_they_are(value):
    assert canonicalize(value) == value and type(canonicalize(value)) is type(value)


def test_a_bool_is_not_turned_into_an_int():
    assert canonicalize(True) is True


def test_missing_values_are_marked_by_kind():
    assert (
        canonicalize(float("nan")) == {"$na": "nan"}
        and canonicalize(pd.NA) == {"$na": "NA"}
        and canonicalize(pd.NaT) == {"$na": "NaT"}
    )
    assert canonicalize(float("nan")) != canonicalize(pd.NA)


def test_infinity_decimal_bytes_and_numpy_scalars():
    assert canonicalize(float("inf")) == {"$float": "inf"}
    assert canonicalize(decimal.Decimal("1.50")) == {"$decimal": "1.50"}
    assert canonicalize(b"\x00\xff") == {"$bytes": "AP8="}
    assert canonicalize(np.int64(3)) == 3 and type(canonicalize(np.int64(3))) is int
    assert canonicalize(np.float64(2.5)) == 2.5 and canonicalize(np.bool_(True)) is True


def test_dates_times_and_timestamps_keep_their_offset():
    aware = datetime.datetime(
        2022, 1, 17, 18, 11, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert canonicalize(aware)["$datetime"] == "2022-01-17T18:11:30-05:00"
    assert canonicalize(datetime.datetime(2022, 1, 17)) == {
        "$datetime": "2022-01-17T00:00:00",
        "$tz": None,
    }
    assert canonicalize(pd.Timestamp("2022-01-17 18:11:30")) == {
        "$datetime": "2022-01-17T18:11:30",
        "$tz": None,
    }
    assert canonicalize(datetime.date(2022, 1, 17)) == {"$date": "2022-01-17"}
    assert canonicalize(datetime.timedelta(minutes=5)) == {"$timedelta_seconds": 300.0}


def test_a_data_frame_keeps_its_columns_dtypes_index_and_cells():
    df = pd.DataFrame(
        {
            "a": pd.array([1, None], dtype="Int64"),
            "b": ["x", None],
            "c": pd.to_datetime(["2021-10-01", None]),
        }
    )
    result = canonicalize(df)["$dataframe"]
    assert result["columns"] == ["a", "b", "c"]
    assert result["dtypes"] == {"a": "Int64", "b": "object", "c": "datetime64[ns]"}
    assert result["index"] == [0, 1]
    assert result["values"] == [
        [1, "x", {"$datetime": "2021-10-01T00:00:00", "$tz": None}],
        [{"$na": "NA"}, None, {"$na": "NaT"}],
    ]


def test_two_data_frames_that_differ_only_in_dtype_are_different():
    assert canonicalize(pd.DataFrame({"a": [1]})) != canonicalize(
        pd.DataFrame({"a": [1.0]})
    )
    assert canonicalize(pd.DataFrame({"a": [1]})) != canonicalize(
        pd.DataFrame({"a": pd.array([1], dtype="Int64")})
    )


def test_a_series_a_tuple_a_set_and_a_dict():
    assert canonicalize(pd.Series([1, 2], name="n"))["$series"]["dtype"] == "int64"
    assert canonicalize((1, "a")) == {"$tuple": [1, "a"]} and canonicalize(
        (1, "a")
    ) != canonicalize([1, "a"])
    assert canonicalize({3, 1, 2}) == {"$set": [1, 2, 3]}
    assert canonicalize({"k": (1, None)}) == {"k": {"$tuple": [1, None]}}


def test_an_unknown_object_is_recorded_with_its_type_so_it_shows_up_as_a_difference():
    class Strange:
        def __repr__(self):
            return "<strange>"

    assert canonicalize(Strange()) == {"$repr": "<strange>", "$type": "Strange"}


def test_the_canonical_form_is_always_json():
    df = pd.DataFrame({"a": [1, 2], "b": [decimal.Decimal("1.5"), None]})
    json.dumps(
        canonicalize(
            {"df": df, "when": pd.Timestamp("2021-10-01"), "bytes": b"x", "na": pd.NA}
        )
    )


# ----------------------------------------------------------------------------------------------
# compare and classify
# ----------------------------------------------------------------------------------------------


def result(script="s", records=None, error=None):
    return {
        "variant": "v",
        "script": script,
        "records": [{"name": n, "value": v} for n, v in (records or {}).items()],
        "error": error,
        "seconds": 0.1,
    }


def test_identical_results_have_no_differences():
    r = result(records={"a": 1, "b": {"$dataframe": {"columns": ["x"]}}})
    assert (
        compare_script(
            "s", r, result(records={"a": 1, "b": {"$dataframe": {"columns": ["x"]}}})
        )
        == []
    )


def test_a_different_value_is_reported_with_both_values():
    (diff,) = compare_script("s", result(records={"a": 1}), result(records={"a": 2}))
    assert (diff["kind"], diff["name"], diff["baseline"], diff["candidate"]) == (
        "value differs",
        "a",
        "1",
        "2",
    )


def test_a_record_in_only_one_variant_is_reported():
    kinds = {
        d["kind"]
        for d in compare_script("s", result(records={"a": 1}), result(records={"b": 1}))
    }
    assert kinds == {"record only in baseline", "record only in candidate"}


def test_an_error_in_one_variant_and_a_value_in_the_other_is_an_error_difference():
    (diff,) = compare_script(
        "s",
        result(records={"a": {"$error": {"type": "X", "message": "m"}}}),
        result(records={"a": 5}),
    )
    assert diff["kind"] == "error differs"
    (diff,) = compare_script(
        "s",
        result(records={"a": {"$error": {"type": "X", "message": "m"}}}),
        result(records={"a": {"$error": {"type": "X", "message": "other"}}}),
    )
    assert diff["kind"] == "error differs"


def test_a_script_error_compares_its_type_and_message_and_not_its_traceback():
    base = {"type": "ValueError", "message": "bad", "traceback_tail": ["a"]}
    assert (
        compare_script(
            "s", result(error=base), result(error={**base, "traceback_tail": ["b"]})
        )
        == []
    )
    (diff,) = compare_script("s", result(error=base), result(error=None))
    assert diff["kind"] == "script error"


def test_a_script_that_ran_in_one_variant_only_is_reported():
    kinds = [d["kind"] for d in compare({"a": result("a")}, {"b": result("b")})]
    assert kinds == ["script only in baseline", "script only in candidate"]


def test_matching_classifications_are_attached_and_the_rest_are_unclassified():
    diffs = compare_script(
        "s", result(records={"a": 1, "b": 1}), result(records={"a": 2, "b": 2})
    )
    classify(
        diffs,
        [{"script": "s", "name": "a", "classification": "visual", "note": "repr"}],
    )
    assert {d["name"]: d["classification"] for d in diffs} == {
        "a": "visual",
        "b": "unclassified",
    }
    assert [d["name"] for d in open_differences(diffs)] == ["b"]


def test_a_wildcard_classification_covers_every_script_or_name():
    diffs = compare_script(
        "s", result(records={"a": 1, "b": 1}), result(records={"a": 2, "b": 2})
    )
    classify(
        diffs,
        [
            {
                "script": "*",
                "name": "*",
                "classification": "intentional",
                "note": "decision",
            }
        ],
    )
    assert open_differences(diffs) == []


def test_a_classification_can_be_limited_to_one_kind_of_difference():
    diffs = compare_script("s", result(records={"a": 1}), result(records={"a": 2}))
    classify(
        diffs,
        [
            {
                "script": "s",
                "name": "a",
                "kind": "error differs",
                "classification": "visual",
            }
        ],
    )
    assert diffs[0]["classification"] == "unclassified"


def test_an_escalated_difference_is_still_open_and_an_unknown_classification_is_refused():
    diffs = compare_script("s", result(records={"a": 1}), result(records={"a": 2}))
    classify(diffs, [{"script": "s", "name": "a", "classification": "escalated"}])
    assert len(open_differences(diffs)) == 1
    with pytest.raises(ValueError):
        classify(diffs, [{"script": "s", "name": "a", "classification": "later"}])


def test_result_files_are_loaded_by_script_name_and_the_differences_file_is_skipped(
    tmp_path,
):
    (tmp_path / "one.json").write_text(json.dumps(result("one")), encoding="utf-8")
    (tmp_path / "differences.json").write_text("[]", encoding="utf-8")
    assert list(load(tmp_path)) == ["one"]


def test_a_value_that_cannot_be_read_becomes_a_marker_and_not_a_crash():
    from tools.parity.runner import canonical_or_marker

    class Broken:
        def __repr__(self):
            raise AttributeError("'NoneType' object has no attribute 'Id'")

    marker = canonical_or_marker(Broken())
    assert marker["$unreadable"] == {
        "value_type": "Broken",
        "type": "AttributeError",
        "message": "'NoneType' object has no attribute 'Id'",
    }
    assert canonical_or_marker(5) == 5


def test_an_error_whose_message_is_inside_the_other_variants_gets_a_detail_note():
    base = result(
        records={
            "a": {
                "$error": {
                    "type": "FaultException",
                    "message": "System.ServiceModel.FaultException: Query view doesn't exist.\r\n at X",
                }
            }
        }
    )
    cand = result(
        records={
            "a": {
                "$error": {
                    "type": "ServiceFault",
                    "message": "Query view doesn't exist.",
                }
            }
        }
    )
    (diff,) = compare_script("s", base, cand)
    assert diff["kind"] == "error differs" and "wrapper" in diff["detail"]
    unrelated = result(
        records={"a": {"$error": {"type": "ServiceFault", "message": "something else"}}}
    )
    assert "detail" not in compare_script("s", base, unrelated)[0]


def test_an_int_and_a_float_that_are_equal_in_python_are_still_a_difference():
    assert (
        len(compare_script("s", result(records={"a": 3}), result(records={"a": 3.0})))
        == 1
    )
    assert (
        len(compare_script("s", result(records={"a": 1}), result(records={"a": True})))
        == 1
    )
    assert (
        len(compare_script("s", result(records={"a": 0}), result(records={"a": False})))
        == 1
    )
    assert (
        compare_script(
            "s",
            result(records={"a": {"x": 1, "y": [2.5]}}),
            result(records={"a": {"y": [2.5], "x": 1}}),
        )
        == []
    )  # key order is not


def test_the_wrapper_note_is_only_for_a_baseline_fault_exception():
    fault = {
        "$error": {
            "type": "FaultException[FaultDetail]",
            "message": "System.ServiceModel.FaultException`1[X]: it failed (Fault Detail is ...)",
        }
    }
    other = {
        "$error": {
            "type": "ArgumentException",
            "message": "it failed. Parameter name: localFile\r\n   at CompAnalytics.X",
        }
    }
    cand = {"$error": {"type": "ServiceFault", "message": "it failed"}}
    (with_fault,) = compare_script(
        "s", result(records={"a": fault}), result(records={"a": cand})
    )
    assert "wrapper" in with_fault["detail"]
    (without,) = compare_script(
        "s", result(records={"a": other}), result(records={"a": cand})
    )
    assert (
        "detail" not in without
    )  # a message that merely contains the other is not a wrapper

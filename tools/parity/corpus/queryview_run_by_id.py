"""Run saved QueryViews by id, with and without inputs, including every way an input can be wrong."""

from composapy.queryview.api import QueryView

ids = fixtures["queryview_ids"]


def summary(df):
    return {
        "rows": len(df),
        "columns": list(df.columns),
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
    }


attempt("run_simple", lambda: summary(QueryView.run(ids["qv_simple"])))
attempt("run_simple_row_count", lambda: len(QueryView.run(ids["qv_simple"])))
attempt("run_missing_id", lambda: QueryView.run(0))
attempt("run_with_error_in_query", lambda: QueryView.run(ids["qv_error"]))
attempt("run_not_an_id", lambda: QueryView.run("not an id"))

attempt(
    "inputs_literals_and_searches",
    lambda: summary(
        QueryView.run(
            ids["qv_inputs"],
            inputs={
                "ageSearchInput": 60,
                "raceLiteralInput": "Asian",
                "genderSearchInput": ("M", "!="),
                "redLiteralInput": False,
                "dateSearchInput": ("2010-05-17", "="),
            },
        )
    ),
)
attempt(
    "inputs_race_values",
    lambda: sorted(
        set(
            QueryView.run(
                ids["qv_inputs"],
                inputs={
                    "ageSearchInput": 60,
                    "raceLiteralInput": "Asian",
                    "genderSearchInput": ("M", "!="),
                    "redLiteralInput": False,
                    "dateSearchInput": ("2010-05-17", "="),
                },
            )["race"]
        )
    ),
)
attempt(
    "inputs_defaults_only", lambda: summary(QueryView.run(ids["qv_inputs"], inputs={}))
)
attempt("inputs_none", lambda: summary(QueryView.run(ids["qv_inputs"], inputs=None)))
attempt(
    "inputs_multichoice",
    lambda: sorted(
        set(
            QueryView.run(
                ids["qv_multichoice"],
                inputs={
                    "genderLiteralInput": [{"M", "U"}],
                    "ageLiteralInput": [{33, 34, 45}],
                },
            )["gender"]
        )
    ),
)
attempt(
    "inputs_multichoice_summary",
    lambda: summary(
        QueryView.run(
            ids["qv_multichoice"],
            inputs={
                "genderLiteralInput": [{"M", "U"}],
                "ageLiteralInput": [{33, 34, 45}],
            },
        )
    ),
)

attempt(
    "inputs_as_a_list",
    lambda: QueryView.run(ids["qv_gender"], inputs=[("genderSearchInput", "M", "!=")]),
)
attempt(
    "inputs_operator_not_known",
    lambda: QueryView.run(ids["qv_gender"], inputs={"genderSearchInput": ("M", ">>")}),
)
attempt(
    "inputs_operator_not_allowed",
    lambda: QueryView.run(ids["qv_age"], inputs={"ageSearchInput": (100, "<=")}),
)
attempt(
    "inputs_name_does_not_exist",
    lambda: QueryView.run(ids["qv_gender"], inputs={"nonexistentInput": ("M", "<=")}),
)
attempt(
    "inputs_value_is_a_dict",
    lambda: QueryView.run(
        ids["qv_gender"], inputs={"genderSearchInput": ({"M": True}, "<=")}
    ),
)
attempt(
    "inputs_value_is_none",
    lambda: QueryView.run(ids["qv_gender"], inputs={"genderSearchInput": (None, "=")}),
)
attempt(
    "inputs_value_wrong_type",
    lambda: QueryView.run(ids["qv_age"], inputs={"ageSearchInput": "old"}),
)
attempt(
    "inputs_float_for_a_number",
    lambda: summary(QueryView.run(ids["qv_age"], inputs={"ageSearchInput": 60.5})),
)
attempt(
    "inputs_bool_for_a_boolean_literal",
    lambda: summary(QueryView.run(ids["qv_inputs"], inputs={"redLiteralInput": True})),
)
attempt(
    "inputs_date_as_datetime",
    lambda: summary(
        QueryView.run(ids["qv_inputs"], inputs={"dateSearchInput": ("2010-05-17", ">")})
    ),
)

from IPython.core.magic import register_cell_magic, register_line_magic
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring


@register_line_magic
def sql(line):
    from composapy.queryview.api import QueryView

    driver = QueryView.driver()
    return driver.run(line)


@magic_arguments()
@argument(
    "-t",
    dest="timeout",
    type=int,
    default=None,
    help="The integer QueryTimeout value (in seconds).",
)
@argument(
    "variable",
    nargs="?",
    type=str,
    default=None,
    help="The name of a variable in which the query output data should be stored. Usual Python restrictions for valid identifiers apply. Note that this will overwrite an existing variable with the same name in the user namespace.",
)
@argument(
    "-s",
    dest="silence",
    action="store_true",
    help="Suppress visible output of the magic command. Defaults to False if unspecified.",
)
@argument(
    "-p",  # "p" for pre-compile
    dest="validate_query",
    action="store_true",
    help="Enable the query validation step. This will result in more informative error messages but can be disabled to improve overall performance.",
)
@argument(
    "-i",
    dest="interactive",
    action="store_true",
    help="Enable interactive table output.",
)
@register_cell_magic
def sql(line, cell):
    from keyword import iskeyword
    from composapy.queryview.api import QueryView

    args = parse_argstring(sql, line)

    driver = QueryView.driver(interactive=args.interactive)
    query = "".join(cell).replace("\n", " ")
    data = driver.run(query, timeout=args.timeout, validate_query=args.validate_query)

    if args.variable is not None and not args.interactive:
        name = args.variable
        if name.isidentifier() and not iskeyword(name):
            get_ipython().user_ns[args.variable] = data
        else:
            print(
                f"WARNING: Could not capture query output. '{args.variable}' is not a valid Python variable name."
            )
    elif args.variable is not None and args.interactive:
        print(
            f"WARNING: Query output cannot be captured when interactive tables are used."
        )

    if args.silence:  # suppress output
        return None

    return data

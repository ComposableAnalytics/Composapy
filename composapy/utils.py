def urljoin(*args):
    """
    Joins given arguments into an url. Trailing but not leading slashes are
    stripped for each argument.
    """

    return "/".join(map(lambda x: str(x).rstrip("/"), args))


def remove_suffix(input_string, suffix):
    """From the python docs, earlier versions of python does not have this."""
    if suffix and input_string.endswith(suffix):
        return input_string[: -len(suffix)]
    return input_string

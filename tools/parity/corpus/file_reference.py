"""Make a file reference from a local file and read what a caller can see of it."""

import json

from composapy.utils import file_ref

ref = file_ref(fixture("create_file_ref_target.txt"))
record("type_name", type(ref).__name__)
record("local_file", ref.LocalFile)
record("uri", str(ref.Uri))
record("uri_absolute", ref.Uri.AbsoluteUri)
record("json", json.dumps(ref))
attempt("str", lambda: str(ref))
attempt("relative_path", lambda: file_ref("no/such/file.txt").LocalFile)
attempt("missing_file_uri", lambda: str(file_ref("C:/no/such/file.txt").Uri))

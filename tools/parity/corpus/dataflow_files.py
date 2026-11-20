"""File inputs to a DataFlow, and file results downloaded from one."""

import hashlib
from pathlib import Path

from composapy.dataflow.api import DataFlow
from composapy.utils import file_ref

DOWNLOADS = (
    Path.cwd() / "downloads"
)  # absolute, in the shared working directory, so both variants write to one place
DOWNLOADS.mkdir(exist_ok=True)
source = fixture("external_input_file.txt")

reader = DataFlow.create(file_path=fixture("external_file_input.json"))


def read_with(value):
    return str(
        reader.run(external_inputs={"my external file input": value})
        .modules.get(name="File Reader")
        .result.value
    )


attempt("input_as_a_path_string", lambda: read_with(source))
attempt("input_as_a_path_object", lambda: read_with(Path(source)))
attempt("input_as_a_file_ref", lambda: read_with(file_ref(source)))
attempt("input_path_does_not_exist", lambda: read_with("C:/no/such/file.txt"))
attempt("input_is_a_directory", lambda: read_with(str(Path(source).parent)))
attempt("input_is_a_number", lambda: read_with(5))
attempt("input_is_none", lambda: read_with(None))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


for flow_file in ("file_writer.json", "csv_writer.json", "xlsx_writer.json"):
    writer = DataFlow.create(file_path=fixture(flow_file))
    label = flow_file.split(".")[0]
    reference = attempt(
        f"{label}.result",
        lambda w=writer: w.run().modules.first().result.value,
        show=lambda r: scrub(r.Uri.OriginalString),
    )
    if reference is None:
        continue
    record(f"{label}.type", type(reference).__name__)
    record(f"{label}.local_file", reference.LocalFile)
    attempt(f"{label}.uri_is_relative", lambda r=reference: not r.Uri.IsAbsoluteUri)
    attempt(
        f"{label}.file_name",
        lambda r=reference: r.Uri.OriginalString.rsplit("/", 1)[-1],
    )
    target = f"{label}-downloaded"
    downloaded = attempt(
        f"{label}.to_file",
        lambda r=reference, t=target: r.to_file(DOWNLOADS, file_name=t),
        show=lambda d: scrub(d.Uri.OriginalString),
    )
    if downloaded is not None:
        record(f"{label}.downloaded.type", type(downloaded).__name__)
        record(f"{label}.downloaded.local_file", downloaded.LocalFile)
        if flow_file.startswith(
            "xlsx"
        ):  # a zip that embeds the time it was written: compare what is in it
            import zipfile

            record(
                f"{label}.downloaded.is_zip", zipfile.is_zipfile(downloaded.LocalFile)
            )
            record(
                f"{label}.downloaded.zip_members",
                sorted(zipfile.ZipFile(downloaded.LocalFile).namelist()),
            )
        else:
            record(f"{label}.downloaded.sha256", digest(downloaded.LocalFile))
        attempt(
            f"{label}.downloaded.uri_is_relative",
            lambda d=downloaded: not d.Uri.IsAbsoluteUri,
        )
    attempt(
        f"{label}.to_file_name_from_uri",
        lambda r=reference: Path(r.to_file(str(DOWNLOADS)).LocalFile).name,
    )
    attempt(
        f"{label}.to_file_into_a_new_folder",
        lambda r=reference: Path(
            r.to_file(DOWNLOADS / "nested" / "deeper", file_name="x").LocalFile
        ).exists(),
    )

attempt("to_file_on_a_local_reference", lambda: file_ref(source).to_file())
reader_ref = (
    DataFlow.create(file_path=fixture("file_writer.json"))
    .run()
    .modules.first()
    .result.value
)
attempt(
    "to_file_into_a_relative_folder",
    lambda: reader_ref.to_file("downloads", file_name="relative-downloaded"),
)
attempt(
    "file_ref_type_by_extension",
    lambda: [
        type(file_ref(source.replace("external_input_file.txt", n))).__name__
        for n in ("external_input_file.txt", "Survey.xlsx")
    ],
)

import subprocess
from pathlib import Path, WindowsPath
import xml.etree.ElementTree as et

from _const import (
    DATALABSERVICE_CSPROJ,
    TF_EXE_PATH,
    XML_NAMESPACE,
)

et.register_namespace("", XML_NAMESPACE)


class CopyFileToSolutionException(Exception):
    pass


class TfsException(Exception):
    pass


def grant_permissions(path: Path) -> None:
    subprocess.check_output(
        ["icacls", f"{path}", "/grant", "Everyone:F", "/t"],
        stderr=subprocess.STDOUT,
    )


def tfs_command(cwd: Path, *args) -> str:
    run = subprocess.run([f"{TF_EXE_PATH}", *args], cwd=cwd, capture_output=True)
    if run.returncode > 1:
        raise TfsException(
            f"Return code greater than 1, failed tf.exe with args: {args} and cwd: {cwd}."
            f"Return Code: {run.returncode}\n"
            f"StdOut: {run.stdout}\n"
            f"StdErr: {run.stderr}\n"
        )
    return run.stdout.decode("utf-8")


def add_to_csproj(wheel: str) -> None:
    tree = et.parse(DATALABSERVICE_CSPROJ)
    root = tree.getroot()

    # this selects the ItemGroup element with sub-element None that has attribute Include
    item_group = root.find(
        f".//{{{XML_NAMESPACE}}}ItemGroup/{{{XML_NAMESPACE}}}None[@Include]/.."
    )

    # add a new None element with an Include attribute equal to the relative wheel path
    relative_wheel_path = str(WindowsPath(f"static/wheels/{wheel}"))
    wheel_element = item_group.find(
        f".//{{{XML_NAMESPACE}}}None[@Include='{relative_wheel_path}']"
    )
    # return if element already exists, no need to add it again. be sure to check for None,
    # __bool__() checks the length of contained nodes to discern true/false
    if wheel_element is not None:
        return

    new_wheel_element = et.Element(f"{{{XML_NAMESPACE}}}None")
    new_wheel_element.set("Include", relative_wheel_path)

    # add the None element to the appropriate ItemGroup element
    item_group.append(new_wheel_element)

    # update the csproj with changes
    tree.write(DATALABSERVICE_CSPROJ)


def remove_from_csproj(wheel: str) -> None:
    tree = et.parse(DATALABSERVICE_CSPROJ)
    root = tree.getroot()

    # this selects the ItemGroup element with sub-element None that has attribute Include
    item_group = root.find(
        f".//{{{XML_NAMESPACE}}}ItemGroup/{{{XML_NAMESPACE}}}None[@Include]/.."
    )

    # this selects the None element with Include attribute equal to relative wheel path
    relative_wheel_path = str(WindowsPath(f"static/wheels/{wheel}"))
    wheel_element = item_group.find(
        f".//{{{XML_NAMESPACE}}}None[@Include='{relative_wheel_path}']"
    )

    # check element exists before removing. be sure to check for None, __bool__() checks the
    # length of contained nodes to discern true/false
    if wheel_element is not None:
        item_group.remove(wheel_element)

    # update the csproj with changes
    tree.write(DATALABSERVICE_CSPROJ)

import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as et
from dataclasses import dataclass, field
from typing import Optional, List

from pydantic import validate_arguments
from pathlib import Path, WindowsPath

from termcolor import colored
from wheel_filename import ParsedWheelFilename, parse_wheel_filename

from _const import (
    DATALABSERVICE_CSPROJ,
    TF_EXE_PATH,
    XML_NAMESPACE,
    DATALABSERVICE_STATIC_DIR,
    DATALABSERVICE_WHEELS_DIR,
    _DEV_COMPOSABLE_PYTHON_EXE,
    COMPOSAPY_ROOT_DIR,
)

et.register_namespace("", XML_NAMESPACE)

TFS_FILE_INFO = []


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


@validate_arguments
@dataclass
class TfsFile:
    local_path: Path
    server_path: str
    changeset: int
    change: Optional[str]
    type: str


def tfs_files_info() -> List[TfsFile]:
    """Tfs does not give a nice object with a bow on top, gives raw text output, so parsing
    must be done to get semantic objects."""
    global TFS_FILE_INFO
    if TFS_FILE_INFO:
        return TFS_FILE_INFO

    tfs_result = tfs_command(DATALABSERVICE_STATIC_DIR, "info", "/recursive", "wheels")

    file_attr_lists = _parse_raw_to_list_of_file_attr_lists(tfs_result)

    local_tfs_files = []
    for local_file_list in file_attr_lists:
        attrs = {}
        for attr_string in local_file_list:
            # regex matches the key : val before a newline
            m = re.match(r"^(?P<_key>[^:]+?)\s*:\s*(?P<_value>.*)$", attr_string)

            # change to snake_case so that attr dictionary unzips to named attrs
            _key = m.group("_key").strip().lower().replace(" ", "_")
            _val = m.group("_value").strip()
            attrs[_key] = _val

        # skip if local_path does not exist or type is not file
        if attrs.get("local_path") and attrs.get("type") == "file":
            # updating change to None for sanity reasons
            attrs["change"] = None if attrs["change"] == "none" else attrs["change"]
            local_tfs_files.append(TfsFile(**attrs))

    TFS_FILE_INFO = local_tfs_files
    return TFS_FILE_INFO


def _parse_raw_to_list_of_file_attr_lists(tfs_result):
    result_strings = [  # split block into rough strings with scope of file
        split_result
        for split_result in tfs_result.split("Local information:")
        if split_result != ""
    ]
    local_file_strings = [  # remove extra unnecessary server information
        result_object.split("Server information:")[0].strip()
        for result_object in result_strings
    ]
    local_files_string_lists = [  # split string into list of key : val attr strings
        file_string.split("\n") for file_string in local_file_strings
    ]
    return local_files_string_lists


@dataclass
class TfsWheel:
    tfs_file: TfsFile
    wheel_info: ParsedWheelFilename

    def remove(self) -> None:
        self._remove_from_tfs()
        self._remove_from_csproj()
        self._remove_from_static_wheels_dir()

    def _remove_from_tfs(self) -> None:
        if not self.tfs_file.change:
            tfs_command(
                DATALABSERVICE_WHEELS_DIR,
                "delete",
                str(self.wheel_info),
            )
        elif "add" in self.tfs_file.change:
            tfs_command(
                DATALABSERVICE_WHEELS_DIR,
                "undo",
                str(self.wheel_info),
            )
        elif "edit" in self.tfs_file.change:
            tfs_command(
                DATALABSERVICE_WHEELS_DIR,
                "undo",
                str(self.wheel_info),
            )
            tfs_command(
                DATALABSERVICE_WHEELS_DIR,
                "delete",
                str(self.wheel_info),
            )

    def _remove_from_csproj(self) -> None:
        tree = et.parse(DATALABSERVICE_CSPROJ)
        root = tree.getroot()

        # this selects the ItemGroup element with sub-element None that has attribute Include
        item_group = root.find(
            f".//{{{XML_NAMESPACE}}}ItemGroup/{{{XML_NAMESPACE}}}None[@Include]/.."
        )

        # this selects the None element with Include attribute equal to relative wheel_info path
        relative_wheel_path = str(WindowsPath(f"static/wheels/{self.wheel_info}"))
        wheel_element = item_group.find(
            f".//{{{XML_NAMESPACE}}}None[@Include='{relative_wheel_path}']"
        )

        # check element exists before removing. be sure to check for None, __bool__() checks the
        # length of contained nodes to discern true/false
        if wheel_element is not None:
            item_group.remove(wheel_element)

        # update the csproj with changes
        tree.write(DATALABSERVICE_CSPROJ)

    def _remove_from_static_wheels_dir(self) -> None:
        try:  # depending on how tfs is feeling that day, may need this. do not remove.
            self.tfs_file.local_path.unlink()
        except:
            pass


@dataclass
class LocalWheel:
    path: Path
    wheel_info: ParsedWheelFilename = field(init=False)

    def __post_init__(self):
        self.wheel_info = parse_wheel_filename(self.path)

    def add(self) -> None:
        self._add_to_static_wheels_dir()
        self._add_to_tfs()
        self._add_to_csproj()
        self._update_requirements_dot_txt()
        self._inline_update_python_venv()

    def _add_to_tfs(self) -> None:
        tfs_command(DATALABSERVICE_WHEELS_DIR, "add", str(self.wheel_info))

    def _add_to_csproj(self) -> None:
        tree = et.parse(DATALABSERVICE_CSPROJ)
        root = tree.getroot()

        # this selects the ItemGroup element with sub-element None that has attribute Include
        item_group = root.find(
            f".//{{{XML_NAMESPACE}}}ItemGroup/{{{XML_NAMESPACE}}}None[@Include]/.."
        )

        # add a new None element with an Include attribute equal to the relative wheel_info path
        relative_wheel_path = str(WindowsPath(f"static/wheels/{self.wheel_info}"))
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

        # pretty print formatting for xml
        _indent(root)

        # update the csproj with changes
        tree.write(DATALABSERVICE_CSPROJ)

    def _add_to_static_wheels_dir(self) -> None:
        shutil.copy(self.path, DATALABSERVICE_WHEELS_DIR)
        grant_permissions(DATALABSERVICE_WHEELS_DIR)

    def _update_requirements_dot_txt(self) -> None:
        req_dot_txt = DATALABSERVICE_STATIC_DIR.joinpath("requirements.txt")

        # package names use dash instead of underscore for requirements.txt
        project_name = self.wheel_info.project.replace("_", "-")

        with open(req_dot_txt, "r") as _file:
            lines = _file.readlines()

        updated_lines = False
        for n, line in enumerate(lines):
            result = re.match(r"(" + project_name + r")(==)?", line)
            if result:
                lines[n] = f"{project_name}\n"
                updated_lines = True
                break  # leave loop once line is updated

        if not updated_lines:
            lines.append(f"{project_name}\n")

        with open(req_dot_txt, "w") as _file:
            _file.writelines(lines)

    def _inline_update_python_venv(self) -> None:
        composapy_wheel_dist_dir = COMPOSAPY_ROOT_DIR.joinpath(".tox", "dist")
        run = subprocess.run(
            [
                f"{_DEV_COMPOSABLE_PYTHON_EXE}",
                "-m",
                "pip",
                "install",
                f"{self.wheel_info.project}=={self.wheel_info.version}",
                "--no-index",
                f"--find-links",
                f"{composapy_wheel_dist_dir.as_posix()}",
            ]
        )
        if run.returncode > 1:
            print(
                f"Failed to update {self.wheel_info.project} package inline. You will need to "
                f"restart the datalabservice to have this change deployed to your python "
                f"environment."
            )


@dataclass
class WheelUpgrade:
    tfs_wheel: TfsWheel
    local_wheel: LocalWheel
    new_wheel: LocalWheel

    def make_upgrade(self):
        try:
            if self.tfs_wheel is None and self.local_wheel is None:
                print(
                    f"Adding {self.new_wheel.wheel_info.project} to project... ", end=""
                )
                self.new_wheel.add()
                print(colored("done.", "green"))

            if (
                self.local_wheel is not None
                and self.local_wheel.wheel_info.version
                == self.new_wheel.wheel_info.version
            ):
                return

            if self.tfs_wheel.wheel_info.version == self.new_wheel.wheel_info.version:
                return

            # only upgrade if new wheel is a different version
            print(
                f"Upgrading {self.tfs_wheel.wheel_info.project} from "
                f"{self.tfs_wheel.wheel_info.version} to "
                f"{self.new_wheel.wheel_info.version}... ",
                end="",
            )
            self.tfs_wheel.remove()
            self.new_wheel.add()
            print(colored("done.", "green"))

        except:
            print(colored("failed.", "red"))


def _indent(elem, level=0) -> None:
    """https://stackoverflow.com/questions/3095434/inserting-newlines-in-xml-file-generated-via-xml-etree-elementtree-in-python"""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            _indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

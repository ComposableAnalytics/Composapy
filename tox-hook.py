import os
from dotenv import dotenv_values
from pathlib import Path
import shutil
import subprocess


composapy_root = Path(__file__).parent
product_root = Path(dotenv_values(".local.env").get("ROOT_PATH_COMPOSABLE")).joinpath(
    "Product"
)


def grant_permissions(path: Path) -> None:
    subprocess.check_output(
        ["icacls", f"{path}", "/grant", "Everyone:F", "/t"],
        stderr=subprocess.STDOUT,
    )


print("Copying composapy-readme.ipynb...")
notebook_src = composapy_root.joinpath("composapy-readme.ipynb")
notebook_dest = product_root.joinpath(
    "CompAnalytics.DataLabService", "static", notebook_src.name
)
shutil.copy(notebook_src, notebook_dest)
grant_permissions(notebook_dest)

print("Copying tests...")
tests_src = composapy_root.joinpath("tests")
tests_dest = product_root.joinpath("UnitTests", "TestData", "composapy")
shutil.copytree(tests_src, tests_dest, dirs_exist_ok=True)
grant_permissions(tests_dest)

print("Copying wheel...")
wheel_src = sorted(composapy_root.joinpath(".tox", "dist").glob("*.whl"))[0]
wheel_dest = product_root.joinpath("CompAnalytics.DataLabService", "static", "wheels")

try:
    old_wheel = sorted(wheel_dest.glob("composapy-*.whl"))[0]
    os.remove(old_wheel)
except IndexError:
    print(
        "Could not find old version of composapy... updating with newly built composapy wheel."
    )

shutil.copy(wheel_src, wheel_dest)
grant_permissions(wheel_dest)

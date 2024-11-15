from loader import _find_dlls
from loader import _load_dlls
from pathlib import Path
import os

dlls = _find_dlls(
    Path("C:/repo/product/CompAnalytics.DataLabService/bin/Debug/"), exclude=[]
)  # returns a set of paths to .dll files
print(dlls)

# example path not absoulte
path = Path("CompAnalytics.DataLabService/bin/Debug/")
print(path)
absolutepath = os.path.abspath(path)
print(absolutepath)
absolutepath2 = path.resolve()
print(absolutepath2)

dlls_test_exclude = _find_dlls(
    Path("C:/repo/product/CompAnalytics.DataLabService/bin/Debug/"),
    exclude=[
        Path("C:/dataLabsArtifacts/dataLabs/"),
        Path("C:/dataLabsArtifacts/python/"),
        Path("C:/dataLabsArtifacts/communalPackages/"),
        Path("C:/repo/"),
    ],
)  # returns a set of paths to .dll files
print(dlls_test_exclude)

# test if they print the same thing
assert dlls == dlls_test_exclude

dlls_in_artifacts = _find_dlls(Path("C:/dataLabsArtifacts/"), exclude=[])
print(dlls_in_artifacts)

# s_load_dlls()

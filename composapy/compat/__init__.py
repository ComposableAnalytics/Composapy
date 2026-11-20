import importlib.abc
import importlib.machinery
import sys
import types

from composapy import contracts

_SERVED = {
    "CompAnalytics": [],
    "CompAnalytics.Contracts": [
        "FileReference",
        "CsvFileReference",
        "ImageReference",
        "KmlReference",
        "KmzReference",
        "StlReference",
        "Mp3Reference",
        "WavReference",
        "VideoReference",
        "AudioReference",
        "ExecutionHandle",
    ],
    "CompAnalytics.Contracts.Tables": ["Table", "TableColumn", "TableColumnCollection"],
    "CompAnalytics.Contracts.QueryView": ["LiteralInput", "SearchInput"],
    "CompAnalytics.Core": ["ContractSerializer"],
}


class CompatFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in _SERVED:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        if fullname.startswith("CompAnalytics."):
            raise ModuleNotFoundError(
                f"No module named '{fullname}'. composapy serves only: "
                + ", ".join(m for m in _SERVED if m != "CompAnalytics"),
                name=fullname,
            )
        return None

    def create_module(self, spec):
        module = types.ModuleType(spec.name)
        module.__path__ = []  # a package, so its children come through this finder too
        for name in _SERVED[spec.name]:
            setattr(module, name, getattr(contracts, name))
        return module

    def exec_module(self, module):
        pass


def install():
    if not any(isinstance(finder, CompatFinder) for finder in sys.meta_path):
        sys.meta_path.append(CompatFinder())

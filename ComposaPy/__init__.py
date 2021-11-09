import os
import clr
from dotenv import load_dotenv, dotenv_values

SETUP_ENV = "../.setup.env"
LOCAL_ENV = "../.local.env"
DLL_ENV = "../.dll.env"

load_dotenv(SETUP_ENV)
load_dotenv(LOCAL_ENV)


def add_dll_reference(name: str, value: str):
    if name.startswith("COMP"):
        value = os.path.join(os.getenv("ROOT_PATH_COMPOSABLE"), value)
    clr.AddReference(value)


for key, path in dotenv_values(DLL_ENV).items():
    add_dll_reference(key, path)

from .ComposaPy import *

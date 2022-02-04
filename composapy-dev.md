# Composapy Dev Environment Setup

## Download [PyCharm](https://www.jetbrains.com/pycharm/) or [VSCode](https://code.visualstudio.com/)

Only use PyCharm if you have a jetbrains license, otherwise your free trial will run out. Note, 
PyCharm IDE is same as IntelliJ IDE.


## Install Py39.x
Click here for [python39.10](https://www.python.org/downloads/release/python-3910/), which is the
most recent at time of writing this document. Note, while other pythons versions may work, py39 
is currently the only officially supported version for development. If you are feeling 
adventurous, stay away from py38; DataLabs is currently set up to manage py38 without the 
use of a virtualenv.

#### Install and upgrade pip/build/twine/tox/tox-wheel.
All of these should be installed BEFORE starting up a virtual environment with tox. 
```
C:\> python -m pip install --upgrade pip
C:\> python -m pip install --upgrade build
C:\> python -m pip install --upgrade twine
C:\> python -m pip install --upgrade tox
C:\> python -m pip install --upgrade tox-wheel
```

## Set up virtualenv with tox

#### Navigate in command prompt or powershell to the project directory root folder, verify your python version (3.9.x).
```
C:\> cd /your/path/to/Composable Analytics/Composapy/Composapy
C:\> python --version
 | >> Python 3.9.X
```

#### Update local settings.

In the root composapy directory, update or create the file `.test.env` with your local settings. 
There may be more than three values in this file, but only the following need to be updated. 
`TEST_API_KEY` can be from any composable web user, such as unittest or unittestadmin.
```
TEST_API_KEY="yourApiKeyHere"
ROOT_PATH_COMPOSABLE="C:/Path/To/Composable Analytics"
```


#### Run tox
```
C:\> python -m tox 
```
Tox will automatically do the following setup for you:
- Create a new directory, `.tox`.
- Create a virtualenv for python39.
- Install packages from requirements.txt.
- Run the tests.
- Build a source tar.gz.

When installing a new package, make sure to update the requirements.txt. Whenever the 
requirements.txt or any configuration files (other than `tox.ini`), you will need to do a `tox 
-r` to run tox with updated requirements.

To build a wheel (`.whl`) instead of source (`.tar.gz`), run `tox --wheel`. Once built, these 
files can be found at `/.tox/dist/`.

## Post-Tox Step

After you have done the previous steps, you can now open the project in your IDE.

#### PyCharm
- Go to `settings -> tools -> terminal -> application settings` and make sure 
that the `Activate Virtualenv` checkbox is selected.
- Set your python interpreter to the python executable located at `/.tox/Scripts/python.exe`.

#### VSCode
- For VSCode, the virtual environment should automatically be detected.
- Set your python interpreter to the python executable located at `/.tox/Scripts/python.exe` 
  (un-tested in VSCode).

## PyPI

To upload the package on PyPI, you will need a user account for [PyPI](https://pypi.org/). You 
will also need to request permissions on the project index so that you can upload.

Although tox will take care of packaging for you, you can read up on packaging 
[here](https://packaging.python.org/en/latest/tutorials/packaging-projects/#packaging-python-projects).

Don't forget to bump the version in `setup.cfg`!

#### Upload archives under `/dist/*` to PyPI -- you will be prompted for credentials.
```
C:\> python -m twine upload /.tox/dist/*
```

## Source Control

After changes and passing tests...
1. Build `composapy-123-xyz.whl`, hook on build should update files inside of Composable 
   Analytics solution. If it does not, refer to notes at end with mention to "catastrophic failure."
2. Write corresponding 2-line tests inside of `NotebookCellExecutionTests.cs`, confirm tests 
   still passing.
3. After check-in to TFS, git push to master (TFS is source of truth, git is for external 
   reference).

In case of catastrophic failure and there is a need to manually update files, the Composable
Analytics project solution has the following Composapy dependencies.
- Binary (wheel): `composapy-123-xyz.whl`, needs to be replaced at 
   `/DataLabService/static/wheels`.
- Notebook: `composapy-readme.ipynb`, if changed, needs to be replaced at 
  `/DataLabService/static`.
- Directory: `/tests/*`, needs to be replaced at `/UnitTests/TestData/composapy`.
  - You can exclude `/.pytest_cache` from `/tests`.

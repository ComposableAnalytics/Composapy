- [Dev Environment Setup](#dev-environment-setup)
  - [Enable Windows Auth](#enable-windows-auth)
  - [Python](#python)
    - [Download Python](#download-python)
    - [Create/Activate Virtual Environment](#createactivate-virtual-environment)
    - [Pip install](#pip-install)
  - [Composapy](#composapy)
    - [Update local .env files](#update-local-env-files)
    - [Tox](#tox)
      - [Black](#black)
      - [Docs](#docs)
      - [Test](#test)
      - [Build](#build)
  - [IDE](#ide)
    - [VSCode](#vscode)
    - [PyCharm](#pycharm)
  - [PyPI](#pypi)
  - [Source Control](#source-control)
    - [Visual Studio Project / Team Foundation Server](#visual-studio-project--team-foundation-server)
    - [Catastrophic Failure](#catastrophic-failure)


# Dev Environment Setup


## Enable Windows Auth

Windows auth is required to run the test suite for Composapy.

1. Windows Key -> search for "turn windows features on or off"
2. `World Wide Web Services` -> `Security` -> Ensure that `Windows Authentication` is checked


## Python


### Download Python

Click [here](https://www.python.org/downloads/release/python-3910/) for the most recent version of 3.9 at time of writing documentation. Add Python to your system path. _Python 3.9 currently the only officially supported version for development, although Python 3.8 no longer has any restrictions on use, as DataLabs is now managed with virtualenv._

Navigate in command prompt or powershell to the Composapy project directory root folder and verify your python version.

```
C:\> cd /your/path/to/Composable Analytics/Composapy/composapy
C:\..\Composapy\Composapy> python --version
Python 3.9.X
```


### Create/Activate Virtual Environment

```
C:\..\Composapy\Composapy> python -m venv dev
C:\..\Composapy\Composapy> .\dev\Scripts\activate
```

After activating, you should see the `(dev)` tag prefixing your console. When you want to deactivate
your virtual environment, you can simply type `deactivate`.

### Pip install

Install the following after activating your virtual environment.

```
(dev) C:\..\Composapy\Composapy> pip install --upgrade pip build twine tox tox-wheel
(dev) C:\..\Composapy\Composapy> pip install -r requirements.txt
```


## Composapy


### Update local .env files

In the Composapy directory, update or create the file `.local.env` (in the same directory as `pyproject.toml`) with your local settings. Include the following in your file:

1. `TEST_API_KEY` : After logging into your development `unittestadmin` on your development instance of Composable, you can generate an api key for the account by going to the unittestadmin [profile](http://localhost/CompApp/UserView.aspx#/?userName=unittestadmin) page and using the `Generate API Token` button to get a new api token.

2. `tf.exe` can be found by hitting windows key, searching for "Developer Command Prompt for VS 
  20XX" and running the command `where tf.exe` (note: when copy-pasting, back-slashes need to be 
  changed to forward-slashes).

  - The location of the tf.exe is different depending on a multitude of variables. If anyone has 
    a script that can be run, which is guaranteed to find the tf.exe, please update to remove 
    this environment variables and call/use that script within `tox-hook.exe`. 

_example/.test.env_
```
TEST_API_KEY="yourApiKeyHere"
TF_EXE_PATH="C:/Path/To/tf.exe"
```


### Tox

```
(dev) C:\..\Composapy\Composapy> tox
```

Composapy uses [tox](https://tox.wiki/en/latest/) for the management of its 
build/testing/deployment needs. Tox creates a virtual environment around your tests/builds, 
separating out any required python versions and environment variables. To run the full suite of 
commands, you can run the tox command without any `-e` specifiers.

When installing a new package, make sure to update the requirements.txt. Whenever the
requirements.txt or any configuration files change (other than `tox.ini`), the `-r` flag will be 
needed to indicate your dependencies have changed and force the recreation of your virtual 
environments.

Each of the tox commands, defined by the `envlist` key (under `[tox]` header), are listed below.


#### Black

```
(dev) C:\..\Composapy\Composapy> tox -e black
```

[Black](https://github.com/psf/black) is an uncompromising linting/code formatting library for 
python.


#### Docs

```
(dev) C:\..\Composapy\Composapy> tox -e docs
```

The docs command uses [jupytext](https://github.com/mwouts/jupytext) and 
[sphinx](https://github.com/sphinx-doc/sphinx) to generate documentation from 
composapy-readme.ipynb and python docstrings. 


#### Test

```
(dev) C:\..\Composapy\Composapy> tox -e py38-test,py39-test,py310-test
```

The test commands (can be run separately or together by using commas between them) run all tests 
in a virtual environment of the specified python version.

Example:

```tox -e py39-test -- tests/test_api.py```

- This is equivalent to running `pytest tests/test_api.py` inside of a python3.9 environment. 
Using `--` allows you to pass arguments to the command (if the command accepts `posargs`).

**Note**: _Make sure all tests are passing before doing any development on Composapy._


#### Build

```
(dev) C:\..\Composapy\Composapy> tox -e build
```

Deploys required resources from the Composapy project to the csharp project, including any 
wheels, tests, and documentation.


#### Tox Usage Examples

```tox -e py39-test -- tests/test_api.py``` : This is equivalent to running 
`pytest tests/test_api.py` inside of a python3.9 environment. Using `--` allows you to pass 
arguments to the command (if the command accepts `posargs`).

```tox -e build```


## IDE 

Do not do your Python development inside of visual studio! You can use one of the following recommendations instead.


### VSCode

[VSCode](https://code.visualstudio.com/) is the free option.

1. `file` -> `preferences` -> `settings` -> search for `default interpreter path` -> use the 
   absolute path to the `python.exe` from the relative Composapy root `dev\Scripts\python.exe`.

2. Click on `Extensions` in the side panel and search/install extension `python-tox`.
   - You can use this extension by doing the VSCode command palette `ctrl-shift-p`, entering `tox` and selecting `select and run tox environment`, then selecting the command you want from the drop down options.

3. Click on `Testing` in the side panel, select `python run configuration`, then choose pytest from the options that appear. This will display your project tests and enable running/debugging them in the UI.


### PyCharm

[PyCharm](https://www.jetbrains.com/pycharm/) is a paid option; for those that happen to have a JetBrains license. _Note: PyCharm and IntelliJ IDEA are essentially the same thing._

1. `file` -> `settings` -> `tools` -> `terminal` -> `application settings`; confirm the `Activate Virtualenv` is checked.

2. Set your python interpreter to the python executable located at `dev\Scripts\python.exe`, now 
   giving you the ability to run commands inside your interpreter without prefixing with python module (`python -m`) command.


## PyPI

_Upload archives under `/dist/*` to PyPI -- you will be prompted for credentials._
```
(dev) C:\..\Composapy\Composapy> python -m twine upload /.tox/dist/*
```

To upload the package on PyPI, you will need a user account for [PyPI](https://pypi.org/). You will also need to request permissions on the project index so that you can upload.

Although tox will take care of packaging for you, you can read up on packaging 
[here](https://packaging.python.org/en/latest/tutorials/packaging-projects/#packaging-python-projects).

Don't forget to bump the version in `setup.cfg`!


## Source Control


### Visual Studio Project / Team Foundation Server

After making changes and confirming tests are passing...

1. Build `composapy-123-xyz.whl`, hook on build should update files inside of Composable 
   Analytics solution. If it does not, refer to notes at end with mention to "catastrophic failure."

2. Write corresponding 2-line tests inside of `NotebookCellExecutionTests.cs`, confirm tests 
   still passing.

3. After check-in to TFS, git push to master (TFS is source of truth, git is for external 
   reference).


### Catastrophic Failure

In case of catastrophic failure and there is a need to manually update files, the Composable Analytics project solution has the following Composapy dependencies.

- Binary (wheel): `composapy-123-xyz.whl`, needs to be replaced at `/DataLabService/static/wheels`.

- Notebook: `composapy-readme.ipynb`, if changed, needs to be replaced at `/DataLabService/static`.

- Directory: `/tests/*`, needs to be replaced at `/UnitTests/TestData/composapy`. _Note: You can exclude_ `/.pytest_cache` _from_ `/tests`.

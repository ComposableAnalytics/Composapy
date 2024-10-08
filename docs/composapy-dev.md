- [Dev Environment Setup](#dev-environment-setup)
  - [Enable Windows Auth](#enable-windows-auth)
  - [Python](#python)
    - [Download Python](#download-python)
    - [Create/Activate Virtual Environment](#createactivate-virtual-environment)
    - [Pip install](#pip-install)
      - [Deactivated Environment](#deactivated-environment)
      - [Activated Environment](#activated-environment)
  - [Composapy](#composapy)
    - [Update local .env files](#update-local-env-files)
    - [Git](#git)
    - [Tox](#tox)
      - [Black](#black)
      - [Docs](#docs)
      - [Test](#test)
      - [Sync Project](#sync-project)
      - [Sync Composapy](#sync-composapy)
      - [Jupyter Lab Upgrade Wheels](#jupyter-lab-upgrade-wheels)
      - [Tox Usage Examples](#tox-usage-examples)
  - [IDE](#ide)
    - [VSCode](#vscode)
    - [PyCharm](#pycharm)
  - [PyPI](#pypi)
  - [Source Control](#source-control)
    - [Git](#git-setup)
    - [Visual Studio Project / Team Foundation Server](#visual-studio-project--team-foundation-server)
    - [Catastrophic Failure](#catastrophic-failure)


# Dev Environment Setup


## Enable Windows Auth

Windows auth is required to run the test suite for Composapy.

1. Windows Key -> search for "turn windows features on or off"
2. `Internet Information Services` -> `World Wide Web Services` -> `Security` -> Ensure that `Windows Authentication` is checked


## Python


### Download Python

Click [here](https://www.python.org/downloads/release/python-3910/) for the most recent version of 3.9 at time of writing documentation. Add Python to your system path. _Although 3.9 is specifically linked above, you will need to download Python 3.8, 3.9, 3.10, and 3.11 to run the full suite of tests._

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

**Important: While the dev environment is useful for development and testing on the fly, make sure to deactivate it before running any tox commands. Failure to do so may cause errors with the initial virtualenv that tox needs to create.**

### Pip install

#### Deactivated Environment

Install the following after deactivating your virtual environment.

```
C:\..\Composapy\Composapy> pip install --upgrade pip build twine tox tox-wheel
```

#### Activated Environment

Reactivate your environment and install the project requirements here. This environment should be
used for python packages related to Composapy during development. It can also be used for 
localized testing, but tox (see below) will do the heavy lifting for automated test environment 
setup and teardown.

```
(dev) C:\..\Composapy\Composapy> pip install -r requirements.txt
```

Keep your virtual environment deactivated for the rest of the readme unless it says otherwise.

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

### Git
Now is a good time to set up Git. See below: [Git Setup](#git-setup)

### Tox

_Composapy uses [tox](https://tox.wiki/en/latest/) for the management of its 
build/testing/deployment needs. Tox creates a virtual environment around your tests/builds, 
separating out any required python versions and environment variables. To run the full suite of 
commands, you can run the tox command without any `-e` specifiers._

_When installing a new package, make sure to update the requirements.txt. Whenever the
requirements.txt or any configuration files change (other than `tox.ini`), the `-r` flag will be 
needed to indicate your dependencies have changed and force the recreation of your virtual 
environments._

_Each of the tox commands, defined by the `envlist` key (under `[tox]` header), are listed below._

_Any commands involving the upgrading/building/deployment of wheels also install those packages
into your local Composable python environment. This removes the need to restart the DataLabService
to update any python packages that were deployed._

```
C:\..\Composapy\Composapy> tox
```

1. Run Black on source code
2. Build the distribution wheel
3. Run tests for python versions...
   - Python3.8
   - Python3.9
   - Python3.10
   - Python3.11
4. Copy over required artifacts into the DataLabService csproj directory so that they are able to be copied over to DataLabs notebook directories
5. Compile `docs\composapy-readme.ipynb` into the `README.md`
6. Compile the docstrings documentation (sphinx-docs) into html for ReadTheDocs (runs `sphinx-build -a -E -b html source build`)
7. Update composapy wheel
   - Copy wheel to Visual Studio project
   - Remove old wheel(s)
   - Update tfs tracking to reflect changes (add/delete/undo)
   - Install wheel inside the local DataLabs environment for continued development
8. Update UnitTest data
   - Copy pytest test files into the Visual Studio project (for c# tests)
   - Add pytest test files to tfs tracking

#### Black

_[Black](https://github.com/psf/black) is an uncompromising linting/code formatting library for 
python._

```
C:\..\Composapy\Composapy> tox -e black
```

1. Run Black on source code.

#### Docs

_The docs command uses [jupytext](https://github.com/mwouts/jupytext) and 
[sphinx](https://github.com/sphinx-doc/sphinx) to generate documentation from 
composapy-readme.ipynb and python docstrings._

```
C:\..\Composapy\Composapy> tox -e docs
```

1. Compile `docs\composapy-readme.ipynb` into the `README.md`
2. Compile the docstrings documentation (sphinx-docs) into html for ReadTheDocs (runs `sphinx-build -a -E -b html source build`)


#### Test

_The test commands (can be run separately or together by using commas between them) run all tests 
in a virtual environment of the specified python version._

```
C:\..\Composapy\Composapy> tox -e py38-test,py39-test,py310-test,py311-test
```

1. Build the distribution wheel.
2. Run tests for python versions...
   - Python3.8
   - Python3.9
   - Python3.10
   - Python3.11

**Note**: _Make sure all tests are passing before doing any development on Composapy._


#### Sync Project

_Deploys required resources from the Composapy project to the csharp project, including any 
wheels, tests, and documentation._

```
C:\..\Composapy\Composapy> tox -e sync-project
```

1. Build the distribution wheel
2. Copy over required artifacts into the DataLabService csproj directory so that they are able to be copied over to DataLabs notebook directories
3. Compile `docs\composapy-readme.ipynb` into the `README.md`
4. Compile the docstrings documentation (sphinx-docs) into html for ReadTheDocs (runs `sphinx-build -a -E -b html source build`)
5. Update composapy wheel
   - Copy wheel to Visual Studio project
   - Remove old wheel(s)
   - Update tfs tracking to reflect changes (add/delete/undo)
   - Install wheel inside the local DataLabs environment for continued development
6. Update UnitTest data
   - Copy pytest test files into the Visual Studio project (for c# tests)
   - Add pytest test files to tfs tracking


**Troubleshooting:** 
Sometimes when running tox commands that involve interacting with TFS, a TFS30063 authorization error occurs. Usually it fails on on `tfs.exe info /recursive wheels`
**Solution:**
   1. Open a command prompt in administrator mode.
   2. Change directory (cd) to `C:\<repo>\Product\CompAnalytics.DataLabService\static` replacing <repo> as needed for your local setup.
   3. Locate the path to the `TF.exe` file, which you should have set in the `.local.env` file.
   4. Run `<PATH TO TF.exe>\tf.exe info /recursive wheels`
   5. A box will pop up prompting you to select a Microsoft account. Use your Composable account to re-authorize TFS. Once the command completes, you can re-run the tox command.

#### Sync Composapy

_Deploys wheel from the Composapy project, but does not deploy the required resources for tests and documentation._

```
C:\..\Composapy\Composapy> tox -e sync-composapy
```

1. Build the distribution wheel
2. Update composapy wheel
   - Copy wheel to Visual Studio project
   - Remove old wheel(s)
   - Update tfs tracking to reflect changes (add/delete/undo)
   - Install wheel inside the local DataLabs environment for continued development


#### Jupyter Lab Upgrade Wheels

_This command downloads the required pinned versions in tox.ini with whatever package 
 is specified inside of the command. It then creates upgrade plans for each wheel in the directory, 
 matching any packages that already currently exist and adding any others that don't. Running this 
 command should be enough to fully update your project, tfs, and the requirements.txt with all 
 needed changes._

_Note: This upgrade command is not run in the default `tox` run command that runs black, tests, and sync-composapy._

```
C:\..\Composapy\Composapy> tox -e upgrade-wheels -- jupyterlab==3.4.5
```


#### Tox Usage Examples

- ```tox -e py39-test -- tests/test_api.py``` : This is equivalent to running 
`pytest tests/test_api.py` inside of a python3.9 environment. Using `--` allows you to pass 
arguments to the command (if the command accepts `posargs`).

- ```tox -e sync-project```



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
(dev) C:\..\Composapy\Composapy> python -m twine upload .tox/dist/*
```

To upload the package on PyPI, you will need a user account for [PyPI](https://pypi.org/). You will also need to request permissions on the project index so that you can upload.

Note that if you have 2-factor authentication enabled on your PyPI account, you will need to use an API token instead of your password. First, log in to PyPI in your browser, go to Account Settings, generate a token, and save it in a safe place. Then, when the above twine command prompts for credentials, use `__token__` as the username and paste in your API token (including the `pypi-` prefix) as the password.

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

### Git Setup
It is imperative that you push to git every time you check in a change to TFS. This ensures that the two repositories remain in sync, which makes it MUCH easier to set up git for future devs.

In a terminal, navigate to the `C:\<path-to-repo>\Composapy\Composapy` directory and run the following commands:
1. `git init`
2. `git remote add origin https://github.com/ComposableAnalytics/Composapy.git`
3. `git checkout -f main`

If these succeed, you should be good to go. Run `git status` to confirm that your local branch is up to date with the remote and there are no changes at all (either unstaged or staged).

### Catastrophic Failure

In case of catastrophic failure and there is a need to manually update files, the Composable Analytics project solution has the following Composapy dependencies.

- Binary (wheel): `composapy-123-xyz.whl`, needs to be replaced at `/DataLabService/static/wheels`.

- Notebook: `composapy-readme.ipynb`, if changed, needs to be replaced at `/DataLabService/static`.

- Directory: `/tests/*`, needs to be replaced at `/UnitTests/TestData/composapy`. _Note: You can exclude_ `/.pytest_cache` _from_ `/tests`.

@ECHO OFF

:: clean up old files to ensure toctrees stay up-to-date across pages
echo|set /p="Force deleting old files... "
del /s /q _sources\* > nul
del /s /q _build\doctrees\* > nul
del /s /q _build\html\* > nul
echo done
echo[

pushd %~dp0

REM Command file for Sphinx documentation

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)
set SOURCEDIR=.
set BUILDDIR=_build

if "%1" == "" goto help

%SPHINXBUILD% >NUL 2>NUL
if errorlevel 9009 (
	echo.
	echo.The 'sphinx-build' command was not found. Make sure you have Sphinx
	echo.installed, then set the SPHINXBUILD environment variable to point
	echo.to the full path of the 'sphinx-build' executable. Alternatively you
	echo.may add the Sphinx directory to PATH.
	echo.
	echo.If you don't have Sphinx installed, grab it from
	echo.https://www.sphinx-doc.org/
	exit /b 1
)

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%

:end
popd

:: ADDITIONS FOR GITHUB PAGES BELOW ::

:: bring \docs\_build\html\ to parent \docs\ directory for consumption by github pages
xcopy .\_build\html\ . /e /y /q
echo.
echo neutrino\docs files have been updated.
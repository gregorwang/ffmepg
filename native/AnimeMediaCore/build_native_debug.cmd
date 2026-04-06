@echo off
call "C:\BuildTools2022\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b %errorlevel%
where cl
if errorlevel 1 exit /b %errorlevel%
"C:\Tools\Codex\cmake\bin\cmake.exe" -S N:\ -B N:\build\Debug-NMake -G "NMake Makefiles"
if errorlevel 1 exit /b %errorlevel%
"C:\Tools\Codex\cmake\bin\cmake.exe" --build N:\build\Debug-NMake --config Debug
exit /b %errorlevel%

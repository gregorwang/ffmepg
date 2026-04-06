@echo off
call "C:\BuildTools2022\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b %errorlevel%
where cl
if errorlevel 1 exit /b %errorlevel%
"C:\Tools\Codex\cmake\bin\cmake.exe" -S N:\ -B N:\build\Release-NMake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b %errorlevel%
"C:\Tools\Codex\cmake\bin\cmake.exe" --build N:\build\Release-NMake
exit /b %errorlevel%

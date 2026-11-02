@echo off
rem Build the C++ benchmark with MSVC Build Tools + Ninja.
rem Usage: scripts\build.bat [DEPS_PREFIX]
rem DEPS_PREFIX must contain include\, lib\, bin\ for libcurl and OpenSSL 3 (default: Anaconda's Library).
setlocal
set "ROOT=%~dp0.."
if "%~1"=="" (set "DEPS_PREFIX=%USERPROFILE%\anaconda3\Library") else (set "DEPS_PREFIX=%~1")
set "VSDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
call "%VSDIR%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "PATH=%VSDIR%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;%VSDIR%\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%"
cmake -S "%ROOT%\cpp" -B "%ROOT%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%DEPS_PREFIX%" || exit /b 1
cmake --build "%ROOT%\build" || exit /b 1
rem Copy runtime DLLs next to the executables.
for %%D in (libcurl.dll libssl-3-x64.dll libcrypto-3-x64.dll zlib.dll libssh2.dll zstd.dll brotlidec.dll brotlicommon.dll) do (
  if exist "%DEPS_PREFIX%\bin\%%D" copy /y "%DEPS_PREFIX%\bin\%%D" "%ROOT%\build\" >nul
)
endlocal

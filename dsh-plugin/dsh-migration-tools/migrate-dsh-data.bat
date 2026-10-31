@echo off
chcp 936 >nul 2>&1
setlocal
title DeepSeek Harness 运行数据迁移

REM ============================================================
REM  DeepSeek Harness 运行数据迁移工具
REM  原理: 数据复制到目标目录并校验后，把源目录改名保留为 .old 备份，
REM        再在原位置创建目录联接(Junction)。程序仍按原路径读写，
REM        无感切换，后续新数据自动落到新位置。
REM  安全: 任一步失败都会自动恢复该项原状；全部成功才创建联接。
REM        无法确认程序是否退出时一律中止，绝不冒险。
REM  数据: %USERPROFILE%\.dsh       会话/存储/配置/凭据
REM        %APPDATA%\@deepseek-ai   桌面端缓存/本地存储/网络状态
REM ============================================================

REM ===== 可按需修改的配置 =====
REM 迁移目标根目录：想放到哪个盘就改这一行（例如 E:\DSHData\migrated）。
set "DESTROOT=D:\DSHData\migrated"
REM 测试用环境变量覆盖（正常使用无需设置）：
if defined DSH_MIG_DEST set "DESTROOT=%DSH_MIG_DEST%"

REM Source can be overridden by the Host launcher (custom DSH_HOME).
set "DSHROOT=%USERPROFILE%\.dsh"
if defined DSH_MIG_SRC set "DSHROOT=%DSH_MIG_SRC%"

set "LOG=%~dp0migrate-dsh-log.txt"

echo ==========================================
echo   DeepSeek Harness 运行数据迁移
echo   目标目录: %DESTROOT%
echo   日志文件: %LOG%
echo ==========================================
echo.

if "%DESTROOT:~0,2%"=="\\" (
    echo [ERROR] UNC targets are not supported by junction migration.
    pause
    exit /b 1
)

if not exist "%DESTROOT:~0,2%\" (
    echo [错误] 找不到目标盘 %DESTROOT:~0,2%，迁移中止。
    pause
    exit /b 1
)

REM ---------- 第 0 步: 确认 DeepSeek Harness 已全部退出 ----------
call :CheckProcesses
if errorlevel 1 (
    echo.
    echo 迁移已中止，未做任何修改。
    pause
    exit /b 1
)

echo.
if not exist "%DESTROOT%\" mkdir "%DESTROOT%" >nul 2>&1
if not exist "%DESTROOT%\" (
    echo [错误] 无法创建目标目录: %DESTROOT%
    pause
    exit /b 1
)
echo ---------- 开始迁移 ----------
echo.

call :MigrateOne "%DSHROOT%" "%DESTROOT%\.dsh" "DSH 主数据（会话/存储/配置/凭据）"
if errorlevel 1 goto :Abort

call :MigrateOne "%APPDATA%\@deepseek-ai" "%DESTROOT%\@deepseek-ai" "桌面端数据（缓存/本地存储/网络状态）"
if errorlevel 1 goto :Abort

echo.
echo ---------- 清理安装包缓存（更新时会重新下载，不影响任何数据）----------
call :CleanDir "%LOCALAPPDATA%\@deepseek-aidsh-desktop-updater"
call :CleanDir "%LOCALAPPDATA%\dsh-desktop-updater"

echo.
echo ==========================================
echo   迁移流程结束
echo ==========================================
echo 下一步:
echo   1. 重新打开 DeepSeek Harness，检查历史会话、登录状态、工作区
echo   2. 确认正常后，回到对话里让我检查并删除 .old 备份
echo   3. 如有异常，退出程序后运行 rollback-dsh-data.bat 回滚
echo.
pause
exit /b 0

:Abort
echo.
echo ==========================================
echo   迁移中止: 上面有失败项，该项已自动恢复原状。
echo   已完成的项保持迁移状态，排除问题后可重新运行本脚本。
echo ==========================================
pause
exit /b 1


REM ============================================================
REM  子程序: CheckProcesses  - 检查 DSH 进程是否已全部退出
REM  读取不到进程列表时视为无法确认，直接中止（失败即安全）。
REM ============================================================
:CheckProcesses
if defined DSH_MIG_TEST (
    echo [测试] 已跳过进程检查。
    exit /b 0
)
set TRY=0
:CheckLoop
tasklist /NH >nul 2>&1
if errorlevel 1 (
    echo [错误] 无法读取进程列表，不能确认 DeepSeek Harness 是否已退出。
    echo        为安全起见迁移中止，未做任何修改。
    echo        请从普通命令提示符窗口运行本脚本后重试。
    exit /b 1
)
tasklist /NH | findstr /I /C:"DeepSeek Harness.exe" /C:"dsh-desktop.exe" /C:"dsh.exe" >nul
if errorlevel 1 (
    echo [检查] DeepSeek Harness 进程已全部退出，可以继续。
    exit /b 0
)
echo.
echo [警告] 检测到 DeepSeek Harness 仍在运行，迁移前必须完全退出：
tasklist /NH | findstr /I /C:"DeepSeek Harness.exe" /C:"dsh-desktop.exe" /C:"dsh.exe"
echo.
echo 请关闭主窗口，并右键系统托盘图标选择退出后：
echo   - 按回车键重新检查
echo   - 输入 A 后回车中止迁移
set "ANS="
set /p "ANS=>"
if /I "%ANS%"=="A" exit /b 1
set /a TRY+=1
if %TRY% GTR 5 (
    echo [错误] 多次检查仍有进程运行，迁移中止。
    exit /b 1
)
goto CheckLoop


REM ============================================================
REM  子程序: MigrateOne  SRC DST LABEL
REM ============================================================
:MigrateOne
set "SRC=%~1"
set "DST=%~2"
set "LABEL=%~3"

echo.
echo ===== %LABEL% =====

fsutil reparsepoint query "%SRC%" >nul 2>&1
if not errorlevel 1 (
    set "CURTARGET="
    for /f "delims=" %%T in ('powershell -NoProfile -Command "(Get-Item -LiteralPath '%SRC%').Target"') do set "CURTARGET=%%T"
    if /I not "%CURTARGET%"=="%DST%" (
        echo [FAIL] Existing junction points somewhere else: %SRC%
        echo        expected: %DST%
        echo        actual:   %CURTARGET%
        exit /b 1
    )
    echo [INFO] Junction already points to the expected target: %SRC%
    exit /b 0
)
if not exist "%SRC%\" (
    echo [跳过] 源目录不存在: %SRC%
    exit /b 0
)

if exist "%DST%\" (
    dir /b "%DST%" 2>nul | findstr /I /V /C:"programmer-workflow" >nul
    if not errorlevel 1 (
        echo [FAIL] Target already contains data: %DST%
        echo        Choose an empty target or inspect it before migrating.
        exit /b 1
    )
)

echo [1/5] 复制数据 ...
robocopy "%SRC%" "%DST%" /E /XJ /COPY:DAT /DCOPY:DAT /R:2 /W:2 /NFL /NDL /NP /LOG+:"%LOG%" /TEE
if errorlevel 8 (
    echo [失败] 复制出错，本项原数据未做任何改动。
    exit /b 1
)

echo [2/5] 校验文件数量 ...
call :CountFiles "%SRC%" SRCC
call :CountFiles "%DST%" DSTC
if not "%SRCC%"=="%DSTC%" (
    echo [失败] 文件数不一致，源 %SRCC% / 目标 %DSTC%，本项原数据未做任何改动。
    echo        可重试本脚本；多次失败请检查目标盘剩余空间。
    exit /b 1
)
echo        文件数校验通过，共 %SRCC% 个文件。

echo [3/5] 重命名源目录为备份 ...
if exist "%SRC%.old\" (
    echo [失败] 备份目录已存在: %SRC%.old
    echo        请先确认上次迁移状态，处理该备份后重试。
    exit /b 1
)
ren "%SRC%" "%~nx1.old" >nul
if errorlevel 1 (
    echo [失败] 无法重命名源目录，可能有文件被占用，本项原数据未做任何改动。
    echo        请确认 DeepSeek Harness 已完全退出后重试。
    exit /b 1
)

echo [4/5] 创建目录联接 ...
mklink /J "%SRC%" "%DST%" >>"%LOG%" 2>&1
if errorlevel 1 (
    echo [失败] 联接创建失败，正在恢复原状 ...
    ren "%SRC%.old" "%~nx1" >nul
    exit /b 1
)

echo [5/5] 验证联接 ...
fsutil reparsepoint query "%SRC%" >nul 2>&1
if errorlevel 1 (
    echo [失败] 联接验证失败，正在恢复原状 ...
    rd "%SRC%" >nul 2>&1
    ren "%SRC%.old" "%~nx1" >nul
    exit /b 1
)
echo migrate-write-test > "%SRC%\.migrate-write-test" 2>nul
if errorlevel 1 (
    echo [失败] 联接写入测试失败，正在恢复原状 ...
    rd "%SRC%" >nul 2>&1
    ren "%SRC%.old" "%~nx1" >nul
    exit /b 1
)
del "%SRC%\.migrate-write-test" >nul 2>&1

echo [完成] %LABEL%
echo        已迁移到: %DST%
echo        原数据备份: %SRC%.old（验证无误后可删除）
exit /b 0


REM ============================================================
REM  子程序: CountFiles  DIR VARNAME  - 递归统计文件数
REM ============================================================
:CountFiles
set "%~2=0"
for /f "delims=" %%f in ('dir /s /b /a:-d "%~1\*" 2^>nul') do set /a %~2+=1
exit /b 0


REM ============================================================
REM  子程序: CleanDir  DIR  - 删除安装包缓存目录
REM ============================================================
:CleanDir
if not exist "%~1\" (
    echo [跳过] 不存在: %~1
    exit /b 0
)
rd /s /q "%~1" >nul 2>&1
if errorlevel 1 (
    echo [警告] 清理失败，可能正在被使用: %~1
) else (
    echo [完成] 已清理: %~1
)
exit /b 0

@echo off
chcp 936 >nul 2>&1
setlocal
title DeepSeek Harness 数据迁移回滚

REM ============================================================
REM  DeepSeek Harness 运行数据迁移回滚工具
REM  作用: 移除各目录联接，把迁移时保留的 .old 备份移回原位置，
REM        使 DeepSeek Harness 完全回到迁移前的状态。
REM  安全: 只处理"是联接"的目录和配套的 .old 备份，不动其他数据。
REM        无法确认程序是否退出时一律中止。
REM  注意: 回滚前请完全退出 DeepSeek Harness（含系统托盘）。
REM ============================================================

REM ===== 配置（必须与迁移时一致）=====
set "DESTROOT=D:\DSHData\migrated"
if defined DSH_MIG_DEST set "DESTROOT=%DSH_MIG_DEST%"

REM Source can be overridden by the Host launcher (custom DSH_HOME).
set "DSHROOT=%USERPROFILE%\.dsh"
if defined DSH_MIG_SRC set "DSHROOT=%DSH_MIG_SRC%"

set "LOG=%~dp0rollback-dsh-log.txt"

echo ==========================================
echo   DeepSeek Harness 数据迁移回滚
echo   日志文件: %LOG%
echo ==========================================
echo.

call :EnsureClosed
if errorlevel 1 (
    pause
    exit /b 1
)

set "FAILED=0"
call :RollbackOne "%DSHROOT%" "%DESTROOT%\.dsh" "DSH data"
if errorlevel 1 set "FAILED=1"
call :RollbackOne "%APPDATA%\@deepseek-ai" "%DESTROOT%\@deepseek-ai" "App data"
if errorlevel 1 set "FAILED=1"

echo.
echo ==========================================
echo   回滚流程结束
echo ==========================================
echo 如以上全部 [完成] / [跳过]，重新打开 DeepSeek Harness 即回到迁移前状态。
echo 目标盘副本仍保留在 %DESTROOT%，确认一切正常后可手动删除。
echo.
if not "%FAILED%"=="0" (
    echo [FAIL] One or more rollback targets failed.
    pause
    exit /b 1
)
pause
exit /b 0


REM ============================================================
REM  子程序: EnsureClosed  - 确认 DSH 已退出；无法确认时中止
REM ============================================================
:EnsureClosed
if defined DSH_MIG_TEST (
    echo [测试] 已跳过进程检查。
    exit /b 0
)
tasklist /NH >nul 2>&1
if errorlevel 1 (
    echo [错误] 无法读取进程列表，不能确认 DeepSeek Harness 是否已退出。
    echo        为安全起见回滚中止，未做任何修改。
    echo        请从普通命令提示符窗口运行本脚本后重试。
    exit /b 1
)
tasklist /NH | findstr /I /C:"DeepSeek Harness.exe" /C:"dsh-desktop.exe" /C:"dsh.exe" >nul
if not errorlevel 1 (
    echo [警告] DeepSeek Harness 仍在运行，请完全退出后再回滚。
    exit /b 1
)
echo [检查] DeepSeek Harness 进程已全部退出，可以继续。
exit /b 0


REM ============================================================
REM  子程序: RollbackOne  SRC DST LABEL
REM ============================================================
:RollbackOne
set "SRC=%~1"
set "DST=%~2"
set "LABEL=%~3"
if not exist "%SRC%\" if not exist "%SRC%.old\" (
    echo [FAIL] Neither source nor backup exists: %SRC%
    exit /b 1
)

echo.
echo ===== %LABEL% =====

if not exist "%SRC%\" (
    if exist "%SRC%.old\" (
        echo [信息] %SRC% 不存在但存在备份，正在移回 ...
        move "%SRC%.old" "%SRC%" >nul
        if errorlevel 1 (
            echo [失败] 移回失败，备份仍在: %SRC%.old
            exit /b 1
        )
        echo [完成] %LABEL% 已恢复到 %SRC%
    ) else (
        echo [跳过] %SRC% 不存在，无需回滚
    )
    exit /b 0
)

fsutil reparsepoint query "%SRC%" >nul 2>&1
if errorlevel 1 (
    echo [跳过] %SRC% 不是联接，未迁移过，保持不动。
    exit /b 0
)

if not exist "%SRC%.old\" (
    echo [警告] 备份 %SRC%.old 不存在，无法自动回滚。
    echo        数据仍在: %DST%
    echo        请手动把该目录内容移回 %SRC% 后再删除联接。
    exit /b 1
)

echo [1/3] 移除目录联接 ...
rd "%SRC%" >nul 2>&1
if errorlevel 1 (
    echo [失败] 无法移除联接: %SRC%
    exit /b 1
)

echo [2/3] 把备份移回原位置 ...
move "%SRC%.old" "%SRC%" >nul
if errorlevel 1 (
    echo [失败] 移回失败，备份仍在: %SRC%.old
    exit /b 1
)

echo [3/3] 校验 ...
if not exist "%SRC%\" (
    echo [失败] 恢复后的目录不存在: %SRC%
    exit /b 1
)
fsutil reparsepoint query "%SRC%" >nul 2>&1
if not errorlevel 1 (
    echo [失败] 恢复后的目录仍是联接，异常，请检查。
    exit /b 1
)

echo [完成] %LABEL% 已恢复到 %SRC%
exit /b 0

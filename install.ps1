# 注册 .buglist 文件关联（只写 HKCU，不需要管理员）
# 同目录有 BUGList.exe 就关联 exe；否则用 buglist.py + pythonw.exe

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $root "BUGList.exe"
$scriptPath = Join-Path $root "buglist.py"
$iconPath = Join-Path $root "assets\buglist.ico"
$progId = "BUGList.file"
$classes = "HKCU:\Software\Classes"

if (Test-Path $exe) {
    $command = ('"{0}" "%1"' -f $exe)
    $icon = ('"{0}",0' -f $exe)
} else {
    if (-not (Test-Path $scriptPath)) { throw "同目录下既没有 BUGList.exe，也没有 buglist.py" }
    $pythonHome = (& python -c "import sys, os; print(os.path.dirname(sys.executable))").Trim()
    $pythonw = Join-Path $pythonHome "pythonw.exe"
    if (-not (Test-Path $pythonw)) { throw "找不到 pythonw.exe，请先安装 Python 3.10+" }
    $command = ('"{0}" "{1}" "%1"' -f $pythonw, $scriptPath)
    if (Test-Path $iconPath) {
        $icon = ('"{0}",0' -f $iconPath)
    } else {
        $icon = ('"{0}",0' -f $pythonw)
    }
}

New-Item -Path "$classes\.buglist" -Force | Out-Null
Set-Item -Path "$classes\.buglist" -Value $progId

New-Item -Path "$classes\$progId" -Force | Out-Null
Set-Item -Path "$classes\$progId" -Value "待修复 BUG 清单"
New-ItemProperty -Path "$classes\$progId" -Name "FriendlyTypeName" -Value "待修复 BUG 清单" -PropertyType String -Force | Out-Null

New-Item -Path "$classes\$progId\DefaultIcon" -Force | Out-Null
Set-Item -Path "$classes\$progId\DefaultIcon" -Value $icon

New-Item -Path "$classes\$progId\shell\open\command" -Force | Out-Null
Set-Item -Path "$classes\$progId\shell\open\command" -Value $command

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class ShellNotify {
    [DllImport("shell32.dll")] public static extern void SHChangeNotify(int eventId, int flags, IntPtr item1, IntPtr item2);
}
'@
[ShellNotify]::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)

Write-Host "已关联 .buglist"
Write-Host "打开方式: $command"

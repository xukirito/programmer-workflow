param(
  [string]$Target = 'screen',
  [string]$Out = '',
  [string]$CopyMode = 'auto',
  [string]$ListMode = '0'
)

$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class PwfWin32 {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")]
  public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")]
  public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")]
  public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
  public static string[] List() {
    var result = new List<string>();
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(512);
      GetWindowText(h, sb, sb.Capacity);
      var title = sb.ToString();
      if (string.IsNullOrWhiteSpace(title)) return true;
      RECT r;
      if (!GetWindowRect(h, out r)) return true;
      uint pid;
      GetWindowThreadProcessId(h, out pid);
      result.Add(title.Replace("\t", " ") + "\t" + r.Left + "\t" + r.Top + "\t" + (r.Right - r.Left) + "\t" + (r.Bottom - r.Top) + "\t" + h.ToInt64() + "\t" + pid);
      return true;
    }, IntPtr.Zero);
    return result.ToArray();
  }
}
"@

function Get-PwfWindows {
  $items = @()
  foreach ($row in [PwfWin32]::List()) {
    $parts = $row -split "`t"
    if ($parts.Count -lt 7) { continue }
    $title = $parts[0]
    $left = [int]$parts[1]
    $top = [int]$parts[2]
    $width = [int]$parts[3]
    $height = [int]$parts[4]
    $handle = [int64]$parts[5]
    $procId = [int]$parts[6]
    if ($width -lt 40 -or $height -lt 40) { continue }
    if ($left -lt -10000 -or $top -lt -10000) { continue }
    if ($title -in @('Program Manager', 'Windows 输入体验', 'Title', 'MSCTFIME UI', 'Default IME')) { continue }
    $process = ''
    try { $process = (Get-Process -Id $procId -ErrorAction Stop).ProcessName } catch { $process = '' }
    $items += [pscustomobject]@{
      title = $title
      process = $process
      handle = $handle
      left = $left
      top = $top
      width = $width
      height = $height
    }
  }
  return @($items | Sort-Object @{ Expression = { $_.width * $_.height }; Descending = $true })
}

function Find-PwfWindow([string]$wanted) {
  $windows = Get-PwfWindows
  if ([string]::IsNullOrWhiteSpace($wanted) -or $wanted -match '^(screen|desktop|full|all|屏幕|全屏|桌面|整个屏幕)$') {
    return $null
  }
  $exact = @($windows | Where-Object { $_.title -ieq $wanted })
  if ($exact.Count -gt 0) { return $exact[0] }
  $contains = @($windows | Where-Object { $_.title -like "*$wanted*" -or $_.process -like "*$wanted*" })
  if ($contains.Count -gt 0) { return $contains[0] }
  return $null
}

$windows = @()
try {
  $windows = Get-PwfWindows
  if ($ListMode -eq '1') {
    $windowList = @($windows | Select-Object -First 40 | ForEach-Object { [pscustomobject]@{ title = $_.title; process = $_.process; width = $_.width; height = $_.height } })
    @{ ok = $true; windows = $windowList } | ConvertTo-Json -Compress -Depth 5
    exit 0
  }

  $fullScreen = [string]::IsNullOrWhiteSpace($Target) -or $Target -match '^(screen|desktop|full|all|屏幕|全屏|桌面|整个屏幕)$'
  $window = Find-PwfWindow $Target
  if (-not $fullScreen -and $null -eq $window) {
    throw ('没有找到匹配的窗口：' + $Target + '；未执行全屏截图。请用 --list 查看可用窗口。')
  }
  if ([string]::IsNullOrWhiteSpace($Out)) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $Out = Join-Path ([System.IO.Path]::GetTempPath()) ("programmer-workflow-shot-" + $stamp + ".png")
  }
  $outDir = [System.IO.Path]::GetDirectoryName($Out)
  if (-not [string]::IsNullOrWhiteSpace($outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }

  $left = 0; $top = 0; $width = 0; $height = 0; $title = 'screen'
  if ($fullScreen) {
    $screen = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $left = $screen.Left; $top = $screen.Top; $width = $screen.Width; $height = $screen.Height
  } else {
    if ($window.width -lt 20 -or $window.height -lt 20) { throw ('window is minimized or too small: ' + $window.title) }
    $left = $window.left; $top = $window.top; $width = $window.width; $height = $window.height
    $title = $window.title
    try { [PwfWin32]::SetForegroundWindow([IntPtr]$window.handle) | Out-Null; Start-Sleep -Milliseconds 180 } catch { }
  }

  $bitmap = New-Object System.Drawing.Bitmap $width, $height
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  try {
    $graphics.CopyFromScreen($left, $top, 0, 0, (New-Object System.Drawing.Size $width, $height))
    $bitmap.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $graphics.Dispose()
  }

  $clipboard = 'none'
  if ($CopyMode -ne 'none') {
    try { [System.Windows.Forms.Clipboard]::SetImage($bitmap); $clipboard = 'image' } catch { $clipboard = 'failed' }
  }
  $bitmap.Dispose()

  @{
    ok = $true
    path = $Out
    window = $title
    width = $width
    height = $height
    recognition = 'model'
    clipboard = $clipboard
  } | ConvertTo-Json -Compress -Depth 5
} catch {
  @{ ok = $false; error = $_.Exception.Message; windows = @($windows | Select-Object -First 12 | ForEach-Object { $_.title }) } | ConvertTo-Json -Compress -Depth 5
  exit 1
}

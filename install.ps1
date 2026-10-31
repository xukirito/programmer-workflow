<#
.SYNOPSIS
  Install Programmer Workflow into one or more coding agents.

.DESCRIPTION
  Copies the portable skill into the user-level or project-level skill directory
  used by each agent. CodeBuddy uses a project-level target
  (`.codebuddy/skills` + `CODEBUDDY.md`). Optionally writes an idempotent
  bootstrap block into the agent's global instruction file so new sessions load
  active memory first.

  The installer never edits files outside the selected target directories and
  the managed bootstrap block. Existing skill directories are skipped unless
  -Force is supplied, in which case they are backed up first.

.EXAMPLE
  .\install.ps1 -DryRun
  .\install.ps1 -Targets agents,claude,kimi -Bootstrap
  .\install.ps1 -Targets project -ProjectRoot "F:\work\my-app"
  .\install.ps1 -Targets codebuddy -ProjectRoot "F:\work\my-app" -Bootstrap
  .\install.ps1 -Targets all -Bootstrap -Force
  .\install.ps1 -Uninstall
#>
[CmdletBinding()]
param(
  [string[]]$Targets = @("agents"),

  [string]$HomeDir = $HOME,
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$HostId = "",

  [switch]$Bootstrap,
  [switch]$Force,
  [switch]$DryRun,
  [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$SkillName = "programmer-workflow"
$Source = Join-Path $PSScriptRoot "skills\$SkillName"
$StartMarker = "<!-- programmer-workflow:start -->"
$EndMarker = "<!-- programmer-workflow:end -->"
$script:HadError = $false

function Write-Step([string]$Message) { Write-Host "  $Message" }
function Write-Section([string]$Message) { Write-Host "`n$Message" -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host "  ! $Message" -ForegroundColor Yellow }
function Write-Done([string]$Message) { Write-Host "  + $Message" -ForegroundColor Green }

function Resolve-FullPath([string]$Path) {
  return [System.IO.Path]::GetFullPath($Path)
}

function Get-TargetPath([string]$Target) {
  switch ($Target) {
    "agents"  { return Join-Path $HomeDir ".agents\skills\$SkillName" }
    "claude"  { return Join-Path $HomeDir ".claude\skills\$SkillName" }
    "kimi"    { return Join-Path $HomeDir ".kimi-code\skills\$SkillName" }
    "codex"   { return Join-Path $HomeDir ".codex\skills\$SkillName" }
    "cursor"  { return Join-Path $HomeDir ".cursor\skills\$SkillName" }
    "dsh"     { return Join-Path $HomeDir ".dsh\skills\$SkillName" }
    "project" { return Join-Path $ProjectRoot ".agents\skills\$SkillName" }
    "codebuddy" { return Join-Path $ProjectRoot ".codebuddy\skills\$SkillName" }
    default   { throw "Unknown target: $Target" }
  }
}

function Get-BootstrapPath([string]$Target) {
  switch ($Target) {
    "agents"  { return Join-Path $HomeDir ".agents\AGENTS.md" }
    "claude"  { return Join-Path $HomeDir ".claude\CLAUDE.md" }
    "kimi"    { return Join-Path $HomeDir ".kimi-code\AGENTS.md" }
    "codex"   { return Join-Path $HomeDir ".codex\AGENTS.md" }
    "dsh"     { return Join-Path $HomeDir ".dsh\AGENTS.md" }
    "project" { return Join-Path $ProjectRoot "AGENTS.md" }
    "codebuddy" { return Join-Path $ProjectRoot "CODEBUDDY.md" }
    default   { return $null }
  }
}

function Get-ExistingTargets {
  $existing = @("agents")
  foreach ($pair in @(
    @("claude", ".claude"), @("kimi", ".kimi-code"), @("codex", ".codex"),
    @("cursor", ".cursor"), @("dsh", ".dsh")
  )) {
    if (Test-Path (Join-Path $HomeDir $pair[1])) { $existing += $pair[0] }
  }
  return $existing
}

function New-Backup([string]$Path) {
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $backup = "$Path.bak-$stamp"
  $n = 1
  while (Test-Path $backup) { $backup = "$Path.bak-$stamp-$n"; $n++ }
  Move-Item -LiteralPath $Path -Destination $backup
  Write-Step "backup: $backup"
}

function Install-Skill([string]$Target) {
  $destination = Resolve-FullPath (Get-TargetPath $Target)
  if ($Uninstall) {
    if (-not (Test-Path $destination)) { Write-Step "not installed: $destination"; return }
    $skillFile = Join-Path $destination "SKILL.md"
    if (-not (Test-Path $skillFile) -or -not ((Get-Content -LiteralPath $skillFile -Raw) -match "name:\s*$SkillName")) {
      Write-Warn "refusing to remove a directory that is not $SkillName`: $destination"
      return
    }
    if ($DryRun) { Write-Step "would remove: $destination"; return }
    Remove-Item -LiteralPath $destination -Recurse -Force
    Write-Done "removed: $destination"
    return
  }
  if ($DryRun) {
    Write-Step "would install: $destination"
    return
  }
  if (Test-Path $destination) {
    if (-not $Force) {
      Write-Step "exists, skipped (use -Force to replace): $destination"
      return
    }
    New-Backup $destination
  }
  New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
  Copy-Item -LiteralPath $Source -Destination $destination -Recurse -Force
  Write-Done "installed: $destination"
}

function Set-ManagedBlock([string]$Path, [string]$Block) {
  $full = Resolve-FullPath $Path
  if ($DryRun) { Write-Step "would write managed block: $full"; return }
  $text = ""
  if (Test-Path $full) {
    $text = [System.IO.File]::ReadAllText($full, [System.Text.Encoding]::UTF8)
  }
  $pattern = "(?s)" + [regex]::Escape($StartMarker) + ".*?" + [regex]::Escape($EndMarker)
  $text = [regex]::Replace($text, $pattern, "").TrimEnd()
  if ($text.Length -gt 0) { $text += "`n`n" }
  $text += $Block.Trim() + "`n"
  New-Item -ItemType Directory -Path (Split-Path -Parent $full) -Force | Out-Null
  [System.IO.File]::WriteAllText($full, $text, [System.Text.UTF8Encoding]::new($false))
  Write-Done "bootstrap: $full"
}

function Remove-ManagedBlock([string]$Path) {
  $full = Resolve-FullPath $Path
  if (-not (Test-Path $full)) { return }
  if ($DryRun) { Write-Step "would remove managed block: $full"; return }
  $text = [System.IO.File]::ReadAllText($full, [System.Text.Encoding]::UTF8)
  $pattern = "(?s)" + [regex]::Escape($StartMarker) + ".*?" + [regex]::Escape($EndMarker)
  $updated = [regex]::Replace($text, $pattern, "").TrimEnd() + "`n"
  [System.IO.File]::WriteAllText($full, $updated, [System.Text.UTF8Encoding]::new($false))
  Write-Done "bootstrap cleaned: $full"
}

function Get-BootstrapBlock([string]$Target, [string]$SkillPath) {
  $hostId = $HostId
  if (-not $hostId) {
    $hostId = switch ($Target) {
      "dsh" { "dsh" }
      "kimi" { "kimi" }
      "codebuddy" { "codebuddy" }
      "claude" { "claude" }
      "cursor" { "cursor" }
      "codex" { "codex" }
      default { "generic" }
    }
  }
  if ($Target -eq "project") {
    # Project-level skills can be used by different agents. Use -HostId when
    # the project belongs to a known host; otherwise use the neutral generic root.
    $portable = ".agents\skills\$SkillName\scripts\companion.py"
    $bootLine = "python `"$portable`" boot --host $hostId --workspace ."
  } elseif ($Target -eq "codebuddy") {
    $portable = ".codebuddy\skills\$SkillName\scripts\companion.py"
    $bootLine = "python `"$portable`" boot --host $hostId --workspace ."
  } else {
    $companion = Join-Path $SkillPath "scripts\companion.py"
    $bootLine = "python `"$companion`" boot --host $hostId --workspace ."
  }
  return @"
$StartMarker
## Programmer Workflow (managed)

At the start of every task, load the ``programmer-workflow`` skill if it is available. Before acting, run:

``````
$bootLine
``````

Obey **active** memory entries. Treat **proposed** entries as suggestions that need the user's approval first. If active memory conflicts with the user's current instruction, ask which one to keep. Follow the skill's ask, stall, debugging, docs and prototype protocols. Do not edit this block by hand; the installer owns it.
$EndMarker
"@
}

if (-not (Test-Path (Join-Path $Source "SKILL.md"))) {
  Write-Error "Skill source not found: $Source"
  exit 1
}

$resolvedHome = Resolve-FullPath $HomeDir
$resolvedProject = Resolve-FullPath $ProjectRoot
$validTargets = @("all", "agents", "claude", "kimi", "codex", "cursor", "dsh", "project", "codebuddy")
$expandedTargets = @()
foreach ($entry in $Targets) {
  foreach ($part in ($entry -split ",")) {
    $trimmed = $part.Trim()
    if (-not $trimmed) { continue }
    if ($validTargets -notcontains $trimmed) {
      Write-Error "Unknown target '$trimmed'. Valid targets: $($validTargets -join ', ')"
      exit 1
    }
    $expandedTargets += $trimmed
  }
}
$targets = @()
if ($expandedTargets -contains "all") {
  $targets = Get-ExistingTargets
} else {
  $targets = $expandedTargets
}
$targets = $targets | Select-Object -Unique

Write-Host "Programmer Workflow installer" -ForegroundColor White
Write-Host "  source : $Source"
Write-Host "  home   : $resolvedHome"
Write-Host "  project: $resolvedProject"
Write-Host "  targets: $($targets -join ', ')"
if ($DryRun) { Write-Host "  mode   : DRY RUN (no changes)" -ForegroundColor Yellow }
if ($Uninstall) { Write-Host "  mode   : UNINSTALL" -ForegroundColor Yellow }

if (-not $Uninstall) {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { Write-Step "python: $($python.Source)" }
  else { Write-Warn "python was not found on PATH; install Python 3.8+ or use the bundled runtime." }
}

foreach ($target in $targets) {
  Write-Section "Target: $target"
  Install-Skill $target
  $bootstrapPath = Get-BootstrapPath $target
  if ($Uninstall) {
    if ($bootstrapPath) { Remove-ManagedBlock $bootstrapPath }
    continue
  }
  if ($Bootstrap -and $bootstrapPath) {
    $skillPath = Resolve-FullPath (Get-TargetPath $target)
    Set-ManagedBlock $bootstrapPath (Get-BootstrapBlock $target $skillPath)
  }
}

Write-Section "Next steps"
if ($Uninstall) {
  Write-Host "  Restart the agent or start a new session to unload the skill."
} else {
  Write-Host "  1. Start a new session (or restart the agent) so the skill catalog refreshes."
  Write-Host "  2. Run: python `"$(Join-Path $Source 'scripts\companion.py')`" doctor"
  Write-Host "  3. Say 'remember ...' or ask for a project summary to trigger the workflow."
  Write-Host "  Kimi Code users can instead run: /plugins install `"$PSScriptRoot`""
}
if ($script:HadError) { exit 1 } else { exit 0 }

#!/usr/bin/env bash
# Programmer Workflow installer for macOS / Linux.
set -eu

SKILL_NAME="programmer-workflow"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/skills/$SKILL_NAME"
START_MARKER="<!-- programmer-workflow:start -->"
END_MARKER="<!-- programmer-workflow:end -->"

HOME_DIR="${HOME:-}"
PROJECT_ROOT="$(pwd)"
TARGETS=""
BOOTSTRAP=0
FORCE=0
DRY_RUN=0
UNINSTALL=0
HOST_ID=""

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --target NAME       agents | claude | kimi | codex | cursor | dsh | project | codebuddy | all
                      Repeatable, comma-separated, or "all".
  --home DIR          User home (default: $HOME)
  --project DIR       Project root for the project/codebuddy targets (default: cwd)
  --host ID           dsh | kimi | codebuddy | claude | cursor | codex | generic
                      (default: target name; project defaults to generic)
  --bootstrap         Add an idempotent managed block to the agent's global
                      instruction file so new sessions run `boot` first.
  --force             Replace an existing skill directory (back it up first).
  --dry-run           Print actions without changing files.
  --uninstall         Remove installed skill directories and managed blocks.
  -h, --help          Show this help.

Examples:
  ./install.sh --dry-run
  ./install.sh --target agents,claude,kimi --bootstrap
  ./install.sh --target project --project ~/code/my-app
  ./install.sh --target codebuddy --project ~/code/my-app
  ./install.sh --target all --bootstrap --force
  ./install.sh --uninstall
EOF
}

die() { echo "error: $*" >&2; exit 1; }
say() { echo "  $*"; }
section() { echo; echo "$*"; }
ok() { echo "  + $*"; }
warn() { echo "  ! $*" >&2; }

validate_target() {
  case "$1" in
    all|agents|claude|kimi|codex|cursor|dsh|project|codebuddy) return 0 ;;
    *) die "unknown target: $1 (use agents, claude, kimi, codex, cursor, dsh, project, codebuddy, all)" ;;
  esac
}

target_path() {
  case "$1" in
    agents)  echo "$HOME_DIR/.agents/skills/$SKILL_NAME" ;;
    claude)  echo "$HOME_DIR/.claude/skills/$SKILL_NAME" ;;
    kimi)    echo "$HOME_DIR/.kimi-code/skills/$SKILL_NAME" ;;
    codex)   echo "$HOME_DIR/.codex/skills/$SKILL_NAME" ;;
    cursor)  echo "$HOME_DIR/.cursor/skills/$SKILL_NAME" ;;
    dsh)     echo "$HOME_DIR/.dsh/skills/$SKILL_NAME" ;;
    project) echo "$PROJECT_ROOT/.agents/skills/$SKILL_NAME" ;;
    codebuddy) echo "$PROJECT_ROOT/.codebuddy/skills/$SKILL_NAME" ;;
    *) die "unknown target: $1" ;;
  esac
}

bootstrap_path() {
  case "$1" in
    agents)  echo "$HOME_DIR/.agents/AGENTS.md" ;;
    claude)  echo "$HOME_DIR/.claude/CLAUDE.md" ;;
    kimi)    echo "$HOME_DIR/.kimi-code/AGENTS.md" ;;
    codex)   echo "$HOME_DIR/.codex/AGENTS.md" ;;
    dsh)     echo "$HOME_DIR/.dsh/AGENTS.md" ;;
    project) echo "$PROJECT_ROOT/AGENTS.md" ;;
    codebuddy) echo "$PROJECT_ROOT/CODEBUDDY.md" ;;
    *) echo "" ;;
  esac
}

existing_targets() {
  local list="agents"
  if [ -d "$HOME_DIR/.claude" ]; then list="$list claude"; fi
  if [ -d "$HOME_DIR/.kimi-code" ]; then list="$list kimi"; fi
  if [ -d "$HOME_DIR/.codex" ]; then list="$list codex"; fi
  if [ -d "$HOME_DIR/.cursor" ]; then list="$list cursor"; fi
  if [ -d "$HOME_DIR/.dsh" ]; then list="$list dsh"; fi
  echo "$list"
}

managed_block() {
  local target="$1" skill_path="$2" host_id="$HOST_ID" boot_line
  if [ -z "$host_id" ]; then
    case "$target" in
      dsh) host_id="dsh" ;; kimi) host_id="kimi" ;; codebuddy) host_id="codebuddy" ;;
      claude) host_id="claude" ;; cursor) host_id="cursor" ;; codex) host_id="codex" ;;
      *) host_id="generic" ;;
    esac
  fi
  if [ "$target" = "project" ]; then
    boot_line="python \".agents/skills/$SKILL_NAME/scripts/companion.py\" boot --host $host_id --workspace ."
  elif [ "$target" = "codebuddy" ]; then
    boot_line="python \".codebuddy/skills/$SKILL_NAME/scripts/companion.py\" boot --host $host_id --workspace ."
  else
    boot_line="python \"$skill_path/scripts/companion.py\" boot --host $host_id --workspace ."
  fi
  cat <<EOF
$START_MARKER
## Programmer Workflow (managed)

At the start of every task, load the \`programmer-workflow\` skill if it is available. Before acting, run:

\`\`\`
$boot_line
\`\`\`

Obey **active** memory entries. Treat **proposed** entries as suggestions that need the user's approval first. If active memory conflicts with the user's current instruction, ask which one to keep. Follow the skill's ask, stall, debugging, docs and prototype protocols. Do not edit this block by hand; the installer owns it.
$END_MARKER
EOF
}

set_managed_block() {
  local file="$1" block="$2"
  if [ "$DRY_RUN" = "1" ]; then say "would write managed block: $file"; return; fi
  mkdir -p "$(dirname "$file")"
  local tmp
  tmp="$(mktemp "${TMPDIR:-/tmp}/wc-block.XXXXXX")"
  if [ -f "$file" ]; then
    awk -v start="$START_MARKER" -v end="$END_MARKER" '
      $0 == start { skip=1; next }
      $0 == end { skip=0; next }
      !skip { print }
    ' "$file" > "$tmp"
    # Collapse runs of blank lines left by the removed block.
    awk 'NF { blank=0; print; next } { blank++; if (blank <= 1) print }' "$tmp" > "$tmp.body"
    mv "$tmp.body" "$tmp"
  fi
  {
    if [ -s "$tmp" ]; then cat "$tmp"; echo; fi
    echo "$block"
  } > "$tmp.new"
  mv "$tmp.new" "$file"
  rm -f "$tmp"
  ok "bootstrap: $file"
}

remove_managed_block() {
  local file="$1"
  [ -f "$file" ] || return 0
  if [ "$DRY_RUN" = "1" ]; then say "would remove managed block: $file"; return; fi
  local tmp
  tmp="$(mktemp "${TMPDIR:-/tmp}/wc-block.XXXXXX")"
  awk -v start="$START_MARKER" -v end="$END_MARKER" '
    $0 == start { skip=1; next }
    $0 == end { skip=0; next }
    !skip { print }
  ' "$file" > "$tmp"
  mv "$tmp" "$file"
  ok "bootstrap cleaned: $file"
}

install_skill() {
  local target="$1" dest
  dest="$(target_path "$target")"
  if [ "$UNINSTALL" = "1" ]; then
    [ -d "$dest" ] || { say "not installed: $dest"; return; }
    if [ ! -f "$dest/SKILL.md" ] || ! grep -q "name:[[:space:]]*$SKILL_NAME" "$dest/SKILL.md"; then
      warn "refusing to remove a directory that is not $SKILL_NAME: $dest"
      return
    fi
    if [ "$DRY_RUN" = "1" ]; then say "would remove: $dest"; return; fi
    rm -rf "$dest"
    ok "removed: $dest"
    return
  fi
  if [ "$DRY_RUN" = "1" ]; then say "would install: $dest"; return; fi
  if [ -e "$dest" ]; then
    if [ "$FORCE" != "1" ]; then say "exists, skipped (use --force to replace): $dest"; return; fi
    local backup="$dest.bak-$(date +%Y%m%d-%H%M%S)"
    mv "$dest" "$backup"
    say "backup: $backup"
  fi
  mkdir -p "$(dirname "$dest")"
  cp -R "$SOURCE" "$dest"
  ok "installed: $dest"
}

# ---------------- parse args ----------------
while [ $# -gt 0 ]; do
  case "$1" in
    --target)
      [ $# -ge 2 ] || die "--target needs a value"
      TARGETS="$TARGETS,$2"; shift 2 ;;
    --target=*)
      TARGETS="$TARGETS,${1#--target=}"; shift ;;
    --home)
      [ $# -ge 2 ] || die "--home needs a value"
      HOME_DIR="$2"; shift 2 ;;
    --home=*)
      HOME_DIR="${1#--home=}"; shift ;;
    --project)
      [ $# -ge 2 ] || die "--project needs a value"
      PROJECT_ROOT="$2"; shift 2 ;;
    --project=*)
      PROJECT_ROOT="${1#--project=}"; shift ;;
    --host)
      [ $# -ge 2 ] || die "--host needs a value"
      HOST_ID="$2"; shift 2 ;;
    --host=*)
      HOST_ID="${1#--host=}"; shift ;;
    --bootstrap) BOOTSTRAP=1; shift ;;
    --force) FORCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

[ -n "$HOME_DIR" ] || die "HOME is not set; pass --home DIR"
[ -f "$SOURCE/SKILL.md" ] || die "skill source not found: $SOURCE"
HOME_DIR="$(cd "$HOME_DIR" 2>/dev/null && pwd)" || die "home directory does not exist: $HOME_DIR"
PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || die "project directory does not exist: $PROJECT_ROOT"

# ---------------- resolve targets ----------------
if [ -z "$TARGETS" ]; then
  TARGETS="agents"
fi
TARGETS="${TARGETS#,}"
FINAL=""
IFS=',' read -r -a RAW <<< "$TARGETS"
for item in "${RAW[@]}"; do
  item="$(echo "$item" | tr -d '[:space:]')"
  [ -n "$item" ] || continue
  validate_target "$item"
  if [ "$item" = "all" ]; then
    FINAL="$(existing_targets)"
    break
  fi
  case " $FINAL " in *" $item "*) ;; *) FINAL="$FINAL $item" ;; esac
done
FINAL="$(echo "$FINAL" | xargs)"

echo "Programmer Workflow installer"
echo "  source : $SOURCE"
echo "  home   : $HOME_DIR"
echo "  project: $PROJECT_ROOT"
echo "  targets: $FINAL"
if [ "$DRY_RUN" = "1" ]; then echo "  mode   : DRY RUN (no changes)"; fi
if [ "$UNINSTALL" = "1" ]; then echo "  mode   : UNINSTALL"; fi

if [ "$UNINSTALL" != "1" ]; then
  if command -v python3 >/dev/null 2>&1; then say "python: $(command -v python3)"
  elif command -v python >/dev/null 2>&1; then say "python: $(command -v python)"
  else warn "python was not found on PATH; install Python 3.8+ or use the bundled runtime."; fi
fi

for target in $FINAL; do
  section "Target: $target"
  install_skill "$target"
  bpath="$(bootstrap_path "$target")"
  if [ "$UNINSTALL" = "1" ]; then
    if [ -n "$bpath" ]; then remove_managed_block "$bpath"; fi
    continue
  fi
  if [ "$BOOTSTRAP" = "1" ] && [ -n "$bpath" ]; then
    skill_path="$(target_path "$target")"
    set_managed_block "$bpath" "$(managed_block "$target" "$skill_path")"
  fi
done

section "Next steps"
if [ "$UNINSTALL" = "1" ]; then
  echo "  Restart the agent or start a new session to unload the skill."
else
  echo "  1. Start a new session (or restart the agent) so the skill catalog refreshes."
  echo "  2. Run: python \"$SOURCE/scripts/companion.py\" doctor"
  echo "  3. Say 'remember ...' or ask for a project summary to trigger the workflow."
  echo "  Kimi Code users can instead run: /plugins install \"$SCRIPT_DIR\""
fi

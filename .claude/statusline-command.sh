#!/usr/bin/env bash
input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

parts=()

if [ -n "$cwd" ]; then
  dir=$(basename "$cwd")
  parts+=("$(printf '\033[34m%s\033[0m' "$dir")")
fi

[ -n "$model" ] && parts+=("$(printf '\033[33m%s\033[0m' "$model")")

if [ -n "$used" ]; then
  used_int=$(printf '%.0f' "$used")
  if [ "$used_int" -ge 80 ]; then
    ctx_color='\033[31m'
  elif [ "$used_int" -ge 50 ]; then
    ctx_color='\033[33m'
  else
    ctx_color='\033[32m'
  fi
  parts+=("$(printf "${ctx_color}ctx:%s%%\033[0m" "$used_int")")
else
  parts+=("$(printf '\033[32mctx:--\033[0m')")
fi

printf '%s' "$(IFS=' | '; echo "${parts[*]}")"

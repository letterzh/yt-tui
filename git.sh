#!/usr/bin/env bash
# Запускает Git с отдельной метапапкой, если обычная .git недоступна.
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec git --git-dir="$PROJECT_DIR/.git-meta" --work-tree="$PROJECT_DIR" "$@"

#!/usr/bin/env bash
# Ensure the Claude CLI native binary is installed and runnable.
set -euo pipefail

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck source=/dev/null
  . "$NVM_DIR/nvm.sh"
fi

if command -v claude >/dev/null 2>&1; then
  bin="$(command -v claude)"
  if file "$bin" 2>/dev/null | grep -qE 'Mach-O|ELF' && claude --version >/dev/null 2>&1; then
    echo "Claude CLI OK: $(claude --version)"
    exit 0
  fi
fi

echo "Repairing Claude CLI..."
npm install -g @anthropic-ai/claude-code --include=optional
echo "Claude CLI OK: $(claude --version)"

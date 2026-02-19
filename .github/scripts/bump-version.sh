#!/usr/bin/env bash
set -eu

CURRENT_VERSION=$(
  grep -E '^[[:space:]]*version[[:space:]]*=' pyproject.toml \
    | head -n1 \
    | sed -E 's/.*version[[:space:]]*=[[:space:]]*"([^"]*)".*/\1/'
)
sed -i "s/version = \"${CURRENT_VERSION}\"/version = \"$1\"/" pyproject.toml

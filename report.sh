#!/usr/bin/env bash
set -euo pipefail

uv run python -m nuubot.sweeps.report "$@"

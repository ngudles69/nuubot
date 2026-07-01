#!/usr/bin/env sh
set -eu

port="${PORT:-5001}"
base_url="http://127.0.0.1:${port}"
out="workspace/logs/server-start.out.log"
err="workspace/logs/server-start.err.log"

is_up() {
    curl -fsS "${base_url}/status" >/dev/null 2>&1
}

if is_up; then
    echo "Server already up at ${base_url}"
    exit 0
fi

mkdir -p workspace/logs
rm -f "$out" "$err" 2>/dev/null || true
uv run python -m nuubot.server "$@" >"$out" 2>"$err" </dev/null &
pid="$!"
echo "starting the server ...."

sleep 1
i=0
while [ "$i" -lt 20 ]; do
    if is_up; then
        echo "Server is up at ${base_url}"
        exit 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "Server exited before becoming ready. See ${err}" >&2
        exit 1
    fi
    i=$((i + 1))
    sleep 0.5
done

echo "Server is not up. pid=${pid}. See ${err}" >&2
exit 1

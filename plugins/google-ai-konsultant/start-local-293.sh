#!/usr/bin/env bash
set -euo pipefail

bridge_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
client=${CHATGPT_WEB_BIN:-$(command -v chatgpt-web || true)}
if [[ -z "$client" && -x "$HOME/chatgpt-web/run" ]]; then
  client="$HOME/chatgpt-web/run"
fi
if [[ ! -x "$client" ]]; then
  echo 'Ustaw CHATGPT_WEB_BIN na pełną ścieżkę do pliku run z tritao/chatgpt-web.' >&2
  exit 1
fi
if [[ -z "${GH_TOKEN:-}" ]]; then
  if ! command -v gh >/dev/null || ! GH_TOKEN=$(gh auth token); then
    echo 'Zaloguj się przez gh auth login albo ustaw GH_TOKEN.' >&2
    exit 1
  fi
  export GH_TOKEN
fi
if [[ ! -t 0 ]]; then
  echo 'Uruchom tę komendę w lokalnym terminalu.' >&2
  exit 1
fi

# The client opens its dedicated Chrome profile on the local debugging port.
env -u GH_TOKEN "$client" --cdp-url http://127.0.0.1:9222 login
read -r -p 'Po zalogowaniu do ChatGPT w otwartym Chrome naciśnij Enter. ' _
exec python3 "$bridge_dir/local_chat_continuity.py" --root-issue 293 --chatgpt-web "$client"

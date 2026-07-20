#!/usr/bin/env bash
# Generated: 2026-07-18 04:17:00 EDT
# Duck SoloPM: lower font-size floor and truthful disabled cursor.
set -Eeuo pipefail

EXPECTED_COMMIT_SHORT="8fc2423"
PATCH_SHA256="d8a3f70a5fc4d32825d0b4b90a5e631a9d41e8d7710f6c73eb9817a315c34d1b"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for command in git sha256sum node python3 docker curl; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || fail "Run this from the duck-solo-pm repository root"

EXPECTED_COMMIT="$(git rev-parse "${EXPECTED_COMMIT_SHORT}^{commit}")"
ACTUAL_COMMIT="$(git rev-parse HEAD)"
[[ "$ACTUAL_COMMIT" == "$EXPECTED_COMMIT" ]] \
  || fail "Expected commit $EXPECTED_COMMIT_SHORT but found $(git rev-parse --short HEAD). Nothing was changed."

expected_sources=(
  "43a6600c97b7ef201a32eae2794abdf1b36854b51cb9ee8e09d092a2d0adfe32 web/static/system-chat.css"
  "fa8c69510adc8fb2da017ceca03ffd09686e7bf7f1a0b4fb9a9005ab8923e0b8 web/static/system-chat.js"
)

for entry in "${expected_sources[@]}"; do
  read -r expected file <<<"$entry"
  [[ -f "$file" ]] || fail "Missing expected source file: $file"
  actual="$(sha256sum "$file" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] \
    || fail "Source mismatch: $file. Nothing was changed."
done

PATCH_FILE="$(mktemp)"
trap 'rm -f "$PATCH_FILE"' EXIT

cat >"$PATCH_FILE" <<'PATCH'
diff --git a/web/static/system-chat.css b/web/static/system-chat.css
index db33aca..2f6f654 100644
--- a/web/static/system-chat.css
+++ b/web/static/system-chat.css
@@ -291,7 +291,7 @@
 
 .duck-system-chat button:disabled,
 .duck-system-chat select:disabled {
-  cursor: wait;
+  cursor: not-allowed;
   opacity: 0.6;
 }
 
diff --git a/web/static/system-chat.js b/web/static/system-chat.js
index 0169729..1173d38 100644
--- a/web/static/system-chat.js
+++ b/web/static/system-chat.js
@@ -33,9 +33,9 @@
 
   const sidebarToggle = document.getElementById('sidebar-toggle');
   const chat = document.querySelector('.duck-system-chat');
-  const fontScales = [0.85, 1, 1.15, 1.3, 1.45];
+  const fontScales = [0.6, 0.7, 0.85, 1, 1.15, 1.3, 1.45];
   const fontScaleKey = 'duck.system-chat.font-scale';
-  let fontScaleIndex = 1;
+  let fontScaleIndex = fontScales.indexOf(1);
 
   function setFontScale(index) {
     fontScaleIndex = Math.max(
PATCH

actual="$(sha256sum "$PATCH_FILE" | awk '{print $1}')"
[[ "$actual" == "$PATCH_SHA256" ]] \
  || fail "Embedded patch checksum failed. Nothing was changed."

git apply --check "$PATCH_FILE" \
  || fail "The correction does not match the installed font controls. Nothing was changed."

BACKUP_TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

for file in web/static/system-chat.css web/static/system-chat.js; do
  backup="${file}.PBAK.${BACKUP_TIMESTAMP}"
  cp --preserve=mode,timestamps "$file" "$backup"
  printf 'Backup created: %s\n' "$backup"
done

git apply "$PATCH_FILE"
printf 'Font-floor correction applied.\n'

node --check web/static/system-chat.js

python3 - <<'PY'
from pathlib import Path

css = Path("web/static/system-chat.css").read_text(encoding="utf-8")
js = Path("web/static/system-chat.js").read_text(encoding="utf-8")

if "[0.6, 0.7, 0.85, 1, 1.15, 1.3, 1.45]" not in js:
    raise SystemExit("Lower font levels were not installed")

if "cursor: not-allowed" not in css:
    raise SystemExit("Disabled cursor correction was not installed")

for path in (
    Path("web/static/system-chat.css"),
    Path("web/static/system-chat.js"),
):
    data = path.read_bytes()
    data.decode("utf-8")
    if any(byte < 32 and byte not in (9, 10, 13) for byte in data):
        raise SystemExit(f"Hidden control character found in {path}")

print("Encoding, syntax, and correction checks passed.")
PY

docker compose config -q
DUCK_UID="$(id -u)" DUCK_GID="$(id -g)" docker compose up -d --build

PORT="${POCKET_PORT:-3200}"
BASE_URL="http://127.0.0.1:${PORT}"
READY=0

for _attempt in {1..40}; do
  if curl -fsS "${BASE_URL}/" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

[[ "$READY" == "1" ]] || fail "Duck did not become ready at ${BASE_URL}"

printf '\nInstalled:\n'
printf '  Font levels: 60%%, 70%%, 85%%, 100%%, 115%%, 130%%, 145%%\n'
printf '  Disabled size limits no longer display a processing cursor\n'
printf '  Duck: %s/\n' "$BASE_URL"

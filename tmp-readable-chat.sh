#!/usr/bin/env bash
# Generated: 2026-07-18 03:33:00 EDT
# Duck SoloPM: reading-first system chat layout.
set -Eeuo pipefail

EXPECTED_COMMIT="5fece1f7376979f2a9d4ec70e0f56bf682b50269"
ARCHIVE_SHA256="b916af90414e794dfc7535e84ae94ef4ca3fa21547dcf7d7b68ed52e87e44828"
PATCH_SHA256="eea19fd881d0f8f91d90572cfe55c153ba1d75623597ea115acc6597859cab01"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for command in git sha256sum base64 gzip node docker curl; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || fail "Run this from the duck-solo-pm repository root"

ACTUAL_COMMIT="$(git rev-parse HEAD)"
[[ "$ACTUAL_COMMIT" == "$EXPECTED_COMMIT" ]] \
  || fail "Expected commit $EXPECTED_COMMIT but found $ACTUAL_COMMIT. Nothing was changed."

expected_sources=(
  "1abe675b31612d9de4e9c43975e9c507d23a1a8a1317d0d31ad3d7fc5a40660f web/static/system-chat.css"
  "10907282955d9fc9467d54980b44e3c96a95831c315168b03b2e2118254e25da web/static/system-chat.js"
  "48c0fbdd86dfa6bef1ccbe16f849a351101268e3d7ff7b8c029b697b43b80c3f web/templates/dashboard.html"
)

for entry in "${expected_sources[@]}"; do
  read -r expected file <<<"$entry"
  [[ -f "$file" ]] || fail "Missing expected source file: $file"
  actual="$(sha256sum "$file" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] \
    || fail "Source mismatch: $file. Nothing was changed."
done

PATCH_ARCHIVE="$(mktemp)"
PATCH_FILE="$(mktemp)"
trap 'rm -f "$PATCH_ARCHIVE" "$PATCH_FILE"' EXIT

base64 --decode >"$PATCH_ARCHIVE" <<'PATCH64'
H4sIAAAAAAACA61Z227jyBF911f0ahJIgkSapESKksfeuWQGGWAHCTKbhyAIdltkU2qbIrnspm1l
1v+e6hvFiyzbwfrBlppd1XU5daqajmmSIMvaUo7wxT3ZXDCOOY0u2IFxsreiHeZ2xBjanHk4oFlM
HtCKRJvAD2w72CwcvEmQ6zjBYjGwLOus7sF0Oj2v/907ZLkzd4Wm7sxz0Lt3A2Q39lgxZrtNjssY
fR8ghHaEbnd8jSKcRmMw4m6HLOQviofJ5WDafxw3n4N4fkfKJM3v12hH45hklwMLoQLHMc22a+TB
PqmmXolSvC/GYfEwQ67t3d3Dn8Do2uDodlvmVRav0ZtkmYQJhvXHAQIP4iq6tRpugPFw0D2N+W6N
9jQbu2Cc1Oo4f1am64di4bLpab2wx+WWZmvkIFzxXC7FlBUpPqzRtqSx9EV8sOBUWObEKvN7tpbb
1S84eY8fxg6cm5QTrWf6Qik3VBYfJU8GVEQmL2NSgunFA2J5SmP0Jl7GEfGkieqpVeKYVnCOa4Le
XXfEei/OSaKPeLDYDsfiZAe5Hpw0F7/K7WY8n6PFHJKOLlAoggs5ESjzwpnno6m3msEGgbPTqbJ2
BIMdKmM1EFzAAPK8Lj6EkRISDb+tTc55vm+5T1zik6fhYc7cuQrldaql2ihPc4jmG281DxYqhkme
cYvR/xIAra+Naq4ZQ1OaEatGku09a0Gh/DYGQG4gvI7UZdY8s9YwLQiWy3DVNUOn9nEwHUyfOtHC
Ead5xuDcaQPQSUqUBzil28yiIAWYiEjGSakgi4s1CmXgz3u0qSAb2ezUDp7n6Qaf3cKqzZ5yURJ6
VwcXK5F/vwuLpVj1WqhowSHaxF6Mm5gxqA+fBL2AsB/OlmgaLOG3APA5nySObirGaXKwIsgJhE6F
1QImLnmb+WQB9eG9/D/QLewEC10PTZfBzFWlpmFxr5EYOgo+nDyAxSXOWJKXoLMqClJGmBH5NCUc
sm2xAkfSGsd2FmTfA9n8HAhMOBhJSaRpGPjM0mzrBY72ubnoGeoB2rNavNxL/emQOX986sO5SP1q
PgtVj+x5uieM4S1hmkHAHVP3TouprcNa03er9XmnW5/I/gzJzjd3TJdlUZmnqaW3Wps0j25N9+w5
gJNNEjWwsVqCC1PXCbUn/cRpTwwT1SkIPZWBYyN0NDqnrX2ivy4D2axAZNIiLyljIn2E/7wP9Hb7
igDjwamsKQTIKcZdSM88X/SZs65ZmDEKZZhxRXsNw1deZy7oYbDuD1ap8ltns4+c2nMrJUm9tZlm
xeY1jo3vTrMlnyn5ft/Wkg1TZIEXuAQGOhZvgvc0PazFd4S+CFqfqc8VtRjstxgpaaLXdPQqqr9b
uChSooOq1z5Ar7v9iqNvcvEznKEfDL+RbU7QP78MjbZafY9Llqf7ZuBfviyb12id0JJxKEmaipFV
AsMLZgEAw1/M5o6mQ50VE1lH658+o7+YPbulSp/fk79gj6zq36qcE4VRY7EqdscOJRX3e3tf0859
/rSd94I986Ylcp7xyV6UtO37ujF0Bx7/hTZGeUyesAAVpQ5BH7gA1n2e5aJFEY2ub5+/wor1D7Kt
UmxA/REmnDzFzEDyJ7ohJRaDDxK7DTJrXdpqdMae1vBdz+Otjq55ab6YuQJ/YSDuWWcmX9GEu3Nv
oAcDzZrTbgMM+v0Omm5xej44OcyfM0YMCEAcWPnbbcXNJuc6cgqD1ZKoYobgwIUTp51JR1K9uXMY
6UXYGAP6i0DB9TkLI2vOyfKMyIVmhzW3odZlQYREjyuvnA3qCHfvAjLBvidmA88xc+ETEW3Mso0h
X2ernoMai8FxsnrT1wb3+YoZigskxXmee2Y0PTVLo9bktXJOpGEettFlQkBWgafnyDaq/AA77etJ
PUWBgLTTh1JYaCpun9Z6sbCsXxxIckbnbouygFu3leawPRUqpmdVFEZJfQmqkSW5AD037XeOZ7wk
PNpdqkfSmJiWRF631iI01R4AGr/gJdHNmXdEN+YV0XyVOBt/YdtOQJwgXL7oFdHNM2+IbswLIl+8
HwpkxsbjCbq6Vi7DxYZxoM2YpOgKxXlU7WHKsLeEf0qJ+Pjh8CUej/rDspAYqQFL6UhAlr1Kh5QY
TS6PdkQpgVy8RoeUaOmox/hXuaOFWpokgb7OoXIvNIiIwwXOQdNwNl/qKlE6GcniV+kUAi2rNG28
SocUkVoEbdEEjX9QKf/9d/SDCrr4VIdOfJHeiw80KyouP0nj5QepcKLqTahTdaeUqs9KBST4+FUe
dPxqTmvuL/fHb/Lc41dxeOObtEB8n5jahWKtyqxJNjpgNCZQ4j/n221KzsVNbwROEDsluOXQUmWy
5GGIzqLPwqUPknzHE8M3jQIgrexu8vhgwz2QsZ9gTLLFWwRMMzYeFWV+A0TCBBenuAAxXUtIqbFF
3/6oXjqAQqP6RzT6u5YcoTUaSWtGLUFG+HvOSwoNgui0IDTCJcVWijdQszOz2FD6bQctpehpRuC0
ANBIiUyaLFxHRXXxLyJZx4jI3NmMH1Jiq8YAXozEkGWsVTGrn33FfGeL65uWlBfkv8qnMzEymOic
VPzrn74refww3mmZRTh5LB5+PSFmpox/gWT/NLiBwHEiKNJaEQs1ioyajeSICcK/SSiONZxniLJP
ZZkLGktwykiNTwXZTma11GVryxExCorjEWUWEUpHtXpNM+5C9mM3CGfLuh2jmgRtuOdB3RjjNNzH
kLMq5XY9vf+in08mlz0NKjg/58XRWtaKWC2ignmH00qU2chkGrUhIkhIC2jSF8F4EMHQZpkFqPPv
j5ftzVA9BYBUltn7ssQHmzL5d6ylbBxFYCWJfzF4nqhALRdycHHmM29eR+pRsoW0aWocgGnz0x1E
SSSAZKSE6It1CH3Dj5ocZNH1RaKURrcgYlqtQiEwZYuN6npBbZaypfjYgP4REQDSce9T/GLQcoZd
dPWiPpkpeBu/MnKPvlZc3rD+toG7PhTNuCMzsXP1RPNMyyxNM9+xISMm3mNUUB/1ymeacjHA/3sk
XRj951Hy+aUqMdktzkQWC2tQY5TRje0epqn8XoAooeV+PPoo2xvfEfMSBEZlgv4CPVJy24+jSV2h
xx6iRt25mJq8xapRWm3AnA5iF+5wqc5x/BEOk18fJ+JPb2w0/z1iF/V/7Owd36d6tnvqsR4e/TDw
wsS37SCYLzaLeX94fFLBcX58cotiGl9cksSfxuR//HlbXL8HVmAMEcDKAckEbKsSSlXjccRU2GPM
McIwSrwHDr2j/GC/vSiu2/reXsT07lrNK41Vfe2h8dXw9Cg4RPxQkKuh2ji8ltl/e6G+XpsC0trg
CCShd0Jb+58rw45obUp3GZ22TdLEsL+5ZWz38bWEVsP4J2z4o8KhQ95cUVG4PlL2s3HTFyoImGJd
ebN2l6tWezLq5UTSzbx5ZTF4SWAlNQ/bKIEKzO/BNr8XUbXuDbuqYXBISbblu6uhCzdcp7cByiIi
uzyFYFwN37NbhBXUBZ5t2+7sv357YZy4HvwP9b4lZUUgAAA=
PATCH64

actual="$(sha256sum "$PATCH_ARCHIVE" | awk '{print $1}')"
[[ "$actual" == "$ARCHIVE_SHA256" ]] \
  || fail "Embedded archive checksum failed. Nothing was changed."

gzip --decompress --stdout "$PATCH_ARCHIVE" >"$PATCH_FILE" \
  || fail "Embedded patch could not be decompressed. Nothing was changed."

actual="$(sha256sum "$PATCH_FILE" | awk '{print $1}')"
[[ "$actual" == "$PATCH_SHA256" ]] \
  || fail "Embedded patch checksum failed. Nothing was changed."

git apply --check "$PATCH_FILE" \
  || fail "The readability patch does not match the installed system chat. Nothing was changed."

BACKUP_TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
targets=(
  web/static/system-chat.css
  web/static/system-chat.js
  web/templates/dashboard.html
)

for file in "${targets[@]}"; do
  backup="${file}.PBAK.${BACKUP_TIMESTAMP}"
  cp --preserve=mode,timestamps "$file" "$backup"
  printf 'Backup created: %s\n' "$backup"
done

git apply "$PATCH_FILE"
printf 'Readability patch applied.\n'

node --check web/static/system-chat.js

python3 - <<'PY'
from pathlib import Path

paths = (
    Path("web/static/system-chat.css"),
    Path("web/static/system-chat.js"),
    Path("web/templates/dashboard.html"),
)

for path in paths:
    data = path.read_bytes()
    data.decode("utf-8")
    controls = [
        byte
        for byte in data
        if byte < 32 and byte not in (9, 10, 13)
    ]
    if controls:
        raise SystemExit(f"Hidden control characters found in {path}")

combined = "\n".join(
    path.read_text(encoding="utf-8")
    for path in paths
)

required = (
    "duck-system-chat-focus",
    "resizeInput",
    "minmax(180px, 1fr)",
    'rows="2"',
)

missing = [
    marker
    for marker in required
    if marker not in combined
]

if missing:
    raise SystemExit(
        "Missing readability markers: "
        + ", ".join(missing)
    )

print("Encoding, syntax, and readability checks passed.")
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
printf '  Reading-first system chat\n'
printf '  Compact header and model controls\n'
printf '  Full-height scrolling answer area\n'
printf '  Compact auto-growing composer\n'
printf '  Prose typography with a centered readable measure\n'
printf '  Focus/Projects control for one-click sidebar switching\n'
printf '  Duck: %s/\n' "$BASE_URL"

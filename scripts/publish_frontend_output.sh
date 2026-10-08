#!/bin/sh
# Publish the built frontend into the live docroot WITHOUT deleting it first.
#
# 2026-10-06: the previous one line took chessguru.ai down.
#
#     rm -rf /output/* && cp -r /build/* /output/
#
# `/output` IS the live docroot, bind-mounted from /var/www/chessguru.ai. That
# command deletes the running site and only then copies the new one in. The `rm`
# emitted "can't remove" errors, the `&&` chain stopped, the copy never ran, and
# the docroot was left with no index.html and an empty static/js. Nginx answered
# every request with a redirect cycle and a 500 until the build was restored by
# hand. deploy.sh meanwhile printed "docroot untouched".
#
# THE RULE: nothing in the live docroot is removed until the replacement is
# staged beside it and checked. The swap is the last step and it is quick.
#
# Staging happens INSIDE /output because that is the only writable mount shared
# with the host; a staging directory elsewhere in the container would be on a
# different filesystem and the final move would stop being a rename.
set -eu

# Overridable only so the script can be exercised against temporary directories
# in a test. In the image both default, and nothing passes them.
BUILD="${BUILD_DIR:-/build}"
OUT="${OUTPUT_DIR:-/output}"
NEW="$OUT/.publish-new"
OLD="$OUT/.publish-old"

# 1. There must be something to publish. An empty or broken build stage used to
#    reach this point and still wipe the site.
[ -f "$BUILD/index.html" ] || {
  echo "REFUSING: $BUILD/index.html is missing -- nothing to publish." >&2
  echo "The live site has not been touched." >&2
  exit 1
}

# 2. Stage the new build beside the live one.
#
# Copied with tar rather than `cp -r "$BUILD"/. "$NEW"/`. The image is Alpine,
# and BusyBox cp does not create intermediate directories for that form -- the
# first real run failed with "can't create
# /output/.publish-new/./stockfish/stockfish.wasm: No such file or directory"
# for every file in a subdirectory. tar creates the tree as it extracts and is
# in BusyBox by default.
rm -rf "$NEW" "$OLD"
mkdir -p "$NEW"
( cd "$BUILD" && tar cf - . ) | ( cd "$NEW" && tar xf - ) || {
  echo "REFUSING: could not stage the build." >&2
  echo "The live site has not been touched." >&2
  rm -rf "$NEW"
  exit 1
}

# 3. Check the staged copy before anything live is moved.
[ -f "$NEW/index.html" ] || {
  echo "REFUSING: staged copy has no index.html." >&2
  echo "The live site has not been touched." >&2
  rm -rf "$NEW"
  exit 1
}

# 4. Swap. Move the live files aside rather than deleting them, so a failure
#    between here and the end leaves them recoverable one directory away.
mkdir -p "$OLD"
for entry in "$OUT"/* "$OUT"/.??*; do
  [ -e "$entry" ] || continue
  case "$entry" in
    "$NEW"|"$OLD") continue ;;
  esac
  mv "$entry" "$OLD"/ 2>/dev/null || true
done

mv "$NEW"/* "$OUT"/ 2>/dev/null || true
# Hidden files in a CRA build are rare but real (.well-known, for instance).
for entry in "$NEW"/.??*; do
  [ -e "$entry" ] || continue
  mv "$entry" "$OUT"/ 2>/dev/null || true
done

# 5. Prove the live docroot is serviceable before throwing the old one away.
if [ ! -f "$OUT/index.html" ]; then
  echo "SWAP FAILED: no index.html in the docroot. Rolling back." >&2
  mv "$OLD"/* "$OUT"/ 2>/dev/null || true
  rm -rf "$NEW" "$OLD"
  exit 1
fi

rm -rf "$NEW" "$OLD"

echo "Frontend published to $OUT"
echo "bundle: $(grep -oE 'main\.[a-f0-9]+\.js' "$OUT/index.html" | head -1)"
ls -la "$OUT" | head -12

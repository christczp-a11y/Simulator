#!/usr/bin/env bash
# Build the editable studio scene from the verified CCSA detailed model.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p work/detailed
archive=work/yaris-detailed-v2j.zip
model_url=https://media.ccsa.gmu.edu/model/2010-toyota-yaris-detailed-v2j.zip
model_hash=f68913788cbe520709323f76214054f16bdbeeb2b7ddd6dad3f4defccb15a2b6e9df62d50146d17809e4155a786082c7
verify() {
    python3 -c 'import hashlib,sys; f=open(sys.argv[1],"rb"); sys.exit(0 if hashlib.file_digest(f,"sha384").hexdigest()==sys.argv[2] else "CCSA v2j checksum mismatch")' "$1" "$model_hash"
}
if [[ ! -f "$archive" ]]; then
    curl --proto '=https' --proto-redir '=https' -fLsS --retry 2 -o "$archive.partial" "$model_url"
    verify "$archive.partial"
    mv "$archive.partial" "$archive"
else
    verify "$archive"
fi
mesh=work/detailed/car.npz
key=2010-toyota-yaris-detailed-v2j/yaris-detailed-v2j.key
if [[ ! -s "$mesh" || ! -f work/detailed/source.sha384 || "$(<work/detailed/source.sha384)" != "$model_hash" ]]; then
    unzip -qo "$archive" "$key" -d work/detailed
    python3 scripts/lsdyna_mesh.py "work/detailed/$key" work/detailed/car-building.npz
    mv work/detailed/car-building.npz "$mesh"
    printf '%s\n' "$model_hash" > work/detailed/source.sha384
fi
renderer=${BLENDER_BIN:-work/blender-4.5.16-linux-x64/blender}
if [[ ! -x "$renderer" ]]; then renderer=$(command -v "${BLENDER_BIN:-blender}"); fi
export BLENDER_USER_RESOURCES="$PWD/work/blender-user"
"$renderer" -b -t "${BLENDER_THREADS:-4}" --python-exit-code 1 -P scripts/ep02_cabin_model.py -- \
    "$mesh" work/cabin-model --history out/ep02-car-speeds/physics/56kmh-history.csv "$@"

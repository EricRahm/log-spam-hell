#!/usr/bin/env bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage:
# normalize.sh log_file_name_1.txt log_file_name_2.txt ...

# Deal w/ BSD sed vs GNU sed
case "$(uname -s)" in
  Darwin|*BSD)
    SED='sed -i "" '
    ;;

  Linux)
    SED='sed -i '
    ;;

  *)
    echo "untested platform"
    SED='sed -i '
    ;;
esac

# Normalizes log files to make collation of warnings easier
# - Remove timestamp stuff, ie "09:54:12   INFO - "
# - Remove PIDs, ie "[Child 12345]". Note: it might be useful to preserve the
#   parent/child distinction.
# - Remove full path in warnings, ie "/builds/slave/buildbot1242/.../build/src"
# - Possibly: Remove hex addresses/values, ie: "0x7fccc5bbd2f0"
normalize_file()
{
  file=$1
  $SED -E -e 's/^[0-9:]+[[:space:]]+INFO[[:space:]]+-[[:space:]]+//g'         \
          -e 's/\[(Child|Parent|GMP|NPAPI)?[[:space:]]?[0-9]+\]/\[NNNNN\]/g'  \
          -e 's/file (\/builds\/.*\/build\/src\/)([^[:space:]]+)/file \2/g'   \
          -e 's/file (\/builds\/.*\/build\/gecko\/)([^[:space:]]+)/file \2/g' \
	  $file
}

for file in "$@"; do
  echo "normalizing file: $file"
  normalize_file "$file"
done

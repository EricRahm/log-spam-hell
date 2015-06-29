#!/usr/bin/env bash

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
# - Remove hex addresses/values, ie: "0x7fccc5bbd2f0"
# - Remove PIDs, ie "[Child 12345]"
# - Remove full path in warnings, ie "/builds/slave/buildbot1242/.../build/src"
normalize_file()
{
  file=$1
  $SED -E -e 's/^[0-9:]+[[:space:]]+INFO[[:space:]]+-[[:space:]]+//g'        \
          -e 's/\[(Child|Parent|GMP|NPAPI)?[[:space:]]?[0-9]+\]/\[NNNNN\]/g' \
          -e 's/file (\/builds\/.*\/build\/src\/)([^[:space:]]+)/file \2/g'  \
          -e 's/file (\/builds\/.*\/build\/gecko\/)([^[:space:]]+)/file \2/g'  \
	  $file
}

for file in "$@"; do
  echo "normalizing file: $file"
  normalize_file "$file"
done

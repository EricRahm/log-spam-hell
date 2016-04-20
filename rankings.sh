#!/usr/bin/env bash

# Creates a Top 40 ranking of warnings by processing all txt files in the CWD
# A raw list is generated and a list per top-level directory is generated

# Use GNU grep (ggrep) on OSX if it's installed
GREP=`which ggrep || which grep`

TOP_40=$($GREP -h 'WARNING' *.log | sort | uniq -c | sort -brn | head -n40)

echo "TOP 40"
echo "======"
echo "$TOP_40"

echo ""

echo "TOP 40 by dir"
echo "============="

DIRS=$(echo "$TOP_40" | $GREP -o -E 'file [^/]+' | sort | uniq | cut -f 2 -d ' ')
for DIR in $DIRS; do 
  WARNINGS="$(echo "$TOP_40" | $GREP "file $DIR" | sort -brn)"
  TALLY=$(echo "$WARNINGS" | sed -e 's/^[[:space:]]*//' | cut -f 1 -d ' '  | paste -s -d '+' - | bc)

  echo "$DIR ($TALLY)"
  for WARNING in "$WARNINGS"; do
    echo "$WARNING"
  done
  echo ""
done

#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Given a warning summary from rankings.sh this will spit out a summary
# suitable for filing a bug.
#
# Example usage:
# warning_details.sh "4532 [NNNNN] WARNING: Shouldn't call SchedulePaint in a detached pres context: file layout/generic/nsFrame.cpp, line 5195"
WARNING=$1

WARNING_TEXT=$(echo "$WARNING" | sed -E -e 's/([0-9]+).*WARNING: (.*)[:,] file ([^,]+), line ([0-9]+).*/\2/')
WARNING_FILE=$(echo "$WARNING" | sed -E -e 's/([0-9]+).*WARNING: (.*)[:,] file ([^,]+), line ([0-9]+).*/\3/')
WARNING_LINE=$(echo "$WARNING" | sed -E -e 's/([0-9]+).*WARNING: (.*)[:,] file ([^,]+), line ([0-9]+).*/\4/')
WARNING_COUNT=$(echo "$WARNING" | sed -E -e 's/([0-9]+).*WARNING: (.*)[:,] file ([^,]+), line ([0-9]+).*/\1/')

JUST_WARNING=$(echo "$WARNING" | sed -E -e 's/[0-9]+.*WARNING: //')

#echo "WARNING = $WARNING_TEXT"
#echo "LOCATION = $WARNING_FILE:$WARNING_LINE"

# round to 100s
WARNING_COUNT=$((WARNING_COUNT + 50))
WARNING_COUNT=$((WARNING_COUNT / 100))
WARNING_COUNT=$((WARNING_COUNT * 100))

# print bug title
printf "%'d instances of \"%s\" emitted from %s during linux64 debug testing\n" \
       	$WARNING_COUNT \
	"$WARNING_TEXT" \
	"$WARNING_FILE"

# Get files w/ warning and counts
WARNING_COUNTS="$(grep -c "$JUST_WARNING" *.txt | sort -brn -k 2 -t ':' | grep -v ':0')"
WARNING_FILES=$(echo "$WARNING_COUNTS" | cut -d ':' -f 1)

# Get tests w/ warning
TESTS="$(cat $WARNING_FILES | python ../assertion_length.py "$JUST_WARNING" | sort -brn)"
TOTAL_TESTS=$(echo "$TESTS" | wc -l)

# Print bug text
echo ""
echo "> $WARNING"
echo ""
echo "This warning [1] shows up in the following test suites:"
echo ""
for SUITE in $WARNING_COUNTS; do
  echo "> $SUITE"
done

echo ""
echo "It shows up in $TOTAL_TESTS tests. A few of the most prevalent:"
echo ""
TOP_10="$(echo "$TESTS" | head -n10 | sed -e 's/^/> /')"
echo "$TOP_10"
echo ""

#TODO(ER): Don't hardcode the m-c checkout or find a better way to get the ID
HG_ID=$(hg -R ~/dev/mozilla-central/ id | cut -d ' ' -f 1)

#TODO(ER): Fudge the line by grepping for it in the local checkout
echo "[1] https://hg.mozilla.org/mozilla-central/annotate/$HG_ID/$WARNING_FILE#l$WARNING_LINE"

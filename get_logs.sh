#!/usr/bin/env bash

# Example usage:
# ./get_logs.sh http://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/mozilla-central-linux64-debug/1433161121/
wget -r -A '.txt.gz' -nd -np $1
gzip -d *.txt.gz

# remove the build log, it's not interesting
rm *build1-*.txt

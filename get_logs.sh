#!/usr/bin/env bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Example usage:
# ./get_logs.sh http://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/mozilla-central-linux64-debug/1433161121/
# or
# ./get_logs.sh http://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/mozilla-central-linux64-debug/1437384384/mozilla-central_ubuntu64_vm-debug_test-cppunit-bm121-tests1-linux64-build2.txt.gz

FILE=$1

wget -r -A '.txt.gz' -nd -np $FILE
gzip -d *.txt.gz

# remove the build log, it's not interesting
rm *build1-*.txt

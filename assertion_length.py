#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Print out the total number of bytes in each test.

from collections import defaultdict
import operator
import re
import sys

testStartRegexp = re.compile('TEST-START \| (.*)')
stackTraceRegexp = re.compile('#[0-9]+:')


def findTestsWithAssertion(assertion):
    inAssert = False
    currTest = None
    currCount = 0
    warningCounts = defaultdict(int)

    def print_sorted_dict(d):
        for k, v in reversed(sorted(d.items(), key=operator.itemgetter(1))):
            print "%d - %s" % (v, k)

    for l in sys.stdin:
        m = testStartRegexp.search(l)
        if m:
            #warningCounts.clear()
            currTest = m.group(1)

        if currTest and assertion in l:
            warningCounts[currTest] += 1


    print_sorted_dict(warningCounts)
    #if currCount:
    #    print "%d - %s" % (currCount, currTest)

if __name__ == "__main__":
    findTestsWithAssertion(sys.argv[1])


#!/bin/bash

#date -d @1437384384 +%Y-%m-%d

# Usage: daily_rankings.sh {path_to_m-c_log_file}
# - Creates a directory for log files
# - Normalizes them
# - Runs top 40 on them

FILE=$1

# If a it's a full path pull off the log file
if [ "${FILE: -6}" == "txt.gz" ]; then
  FILE=`dirname ${FILE}`/
fi
echo $FILE

TIMESTAMP=`basename ${FILE}`
echo $TIMESTAMP

DATE=`date -d @$TIMESTAMP +%Y-%m-%d`
mkdir $DATE
cd $DATE

../get_logs.sh $FILE
../normalize.sh *.txt
../rankings.sh

echo ""
TOTAL_WARNING_COUNT=`cat *.txt | grep -c 'WARNING:'`
echo "TOTAL WARNING COUNT = $TOTAL_WARNING_COUNT"

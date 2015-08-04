# log-spam-hell
Tools for identifying sources of log spam in mozilla build logs

High level usage:
- Go to treeherder: https://treeherder.mozilla.org/#/jobs?repo=mozilla-central
- Choose a *debug* build for the day that's completed, and all tests for the given platform you care about have completed
- Select any test, copy the path to the full log
- Run the `daily_warnings.sh` script:
  `./daily_warnings.sh http://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/mozilla-central-linux64-debug/1438686109/mozilla-central-linux64-debug-bm71-build1-build123.txt.gz`
- Rejoice in the glorious top 40 list, get sad about a new warning, get ready to file a bug by copy and pasting the warning summary and running `warning_details.sh`
  `cd dir_that_was_created_by_daily_warnings && ./warning_details.sh "564 [NNNNN] WARNING: Image width or height is non-positive: file layout/base/nsLayoutUtils.cpp, line 6233"`

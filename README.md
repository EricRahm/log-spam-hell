# log-spam-hell
Tools for identifying sources of log spam in mozilla build logs

High level usage:
- Go to treeherder: https://treeherder.mozilla.org/#/jobs?repo=mozilla-central
- Choose a *debug* build for the day that's completed, and all tests for the given platform you care about have completed
- Copy the revision hash
- Run:
`./treeherder.py fc15477ce628`
- Choose a warning to get more details on:
`./treeherder.py fc15477ce628 'WARNING: Found channel with no loadinfo, assuming third-party request: file dom/base/ThirdPartyUtil.cpp, line 235'`

By default `mozilla-central` is used and the platform is `linux64`.

Other repos such as `mozilla-inbound` or `try` can be substituted using the `--repo` param. Other platforms such as `windowsxp` can be specified as well using the `--platform` param.

```
usage: treeherder.py [-h] [--repo REPO] [--no-cache] [--cache-dir CACHE_DIR]
                     [--warning-count WARNING_COUNT]
                     [--test-summary-count TEST_SUMMARY_COUNT]
                     [--platform PLATFORM] [--reverse] [--create-bug]
                     [--component COMPONENT] [--product PRODUCT]
                     [--api-key API_KEY] [--warning-re WARNING_RE]
                     revision [warning]

positional arguments:
  revision              Revision to retrieve logs for.
  warning               Optional: The text of a warning you want the full
                        details of.

optional arguments:
  -h, --help            show this help message and exit
  --repo REPO           Repository the revision corresponds to. Default:
                        mozilla-central
  --no-cache            Redownload logs if already present.
  --cache-dir CACHE_DIR
                        Directory to cache logs to. Default: <repo>-<revision>
  --warning-count WARNING_COUNT
                        Number of warnings to show in the default summary.
                        Default: 40
  --test-summary-count TEST_SUMMARY_COUNT
                        Number of tests to list in warning summary mode.
                        Default: 10
  --platform PLATFORM   Platform to get logs for. Default: linux64
  --reverse             Print the least common warnings instead.
  --create-bug          Create a new bug for the specified warning.
  --component COMPONENT
                        Component to file the bug in.
  --product PRODUCT     Product to file the bug in. Default: Core
  --api-key API_KEY     The API key to use when creating the bug. Default:
                        extracted from .hgrc
  --warning-re WARNING_RE
                        Regex used to match lines. Can be used to match debug
                        messages that are not proper warnings.
```

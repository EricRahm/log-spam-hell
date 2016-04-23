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

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from setuptools import setup
from logspam import __version__

setup(
    name="mozilla-log-spam",
    version=__version__,
    description="Mozilla test log spam classifier",
    long_description="Tools for identifying the most verbose warnings emitted during testing.",
    url="https://github.com/EricRahm/log-spam-hell",
    author="Eric Rahm",
    author_email="erahm@mozilla.com",
    download_url="https://github.com/EricRahm/log-spam-hell/tarball/%s" % __version__,
    license="MPL 2.0",
    classifiers=[
      "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)"
    ],
    packages=["logspam"],
    install_requires=[
      "mozregression",
      "requests",
      "treeherder-client",
    ],
    entry_points={
      'console_scripts': ['log_spam=logspam.cli_entry:main']
    }
)

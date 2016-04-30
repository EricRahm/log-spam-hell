# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from setuptools import setup

setup(
    name="mozilla-log-spam",
    version="0.0.1",
    description="Mozilla test log spam classifier",
    long_description="Tools for identifying the most verbose warnings emitted during testing.",
    url="https://github.com/EricRahm/log-spam-hell",
    author="Eric Rahm",
    author_email="erahm@mozilla.com",
    license="MPL 2.0",
    classifiers=[
      "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)"
    ],
    #packages=["atsy"],
    install_requires=[
      "requests",
      "treeherder-client",
    ],
    entry_points={
      'console_scripts': ['log_spam=treeherder:main']
    }
)

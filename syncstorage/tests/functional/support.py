# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
""" Base test class, with an instanciated app.
"""

import os
import sys
import optparse
import random
import json
import urlparse

import unittest2
import requests

import macauthlib
import browserid.tests.support

from pyramid.request import Request
from pyramid.interfaces import IAuthenticationPolicy

from mozsvc.tests.support import FunctionalTestCase

from syncstorage.tests.support import StorageTestCase


class StorageFunctionalTestCase(FunctionalTestCase, StorageTestCase):
    """Abstract base class for functional testing of a storage API."""

    def setUp(self):
        super(StorageFunctionalTestCase, self).setUp()

        # Generate userid and auth token crednentials.
        # This can be overridden by subclasses.
        self.config.commit()
        self._authenticate()

        # Monkey-patch the app to sign all requests with the token.
        def new_do_request(req, *args, **kwds):
            macauthlib.sign_request(req, self.auth_token, self.auth_secret)
            return orig_do_request(req, *args, **kwds)
        orig_do_request = self.app.do_request
        self.app.do_request = new_do_request

    def _authenticate(self):
        # For basic testing, use a random uid and sign our own tokens.
        # Subclasses might like to override this and use a live tokenserver.
        self.user_id = random.randint(1, 100000)
        auth_policy = self.config.registry.getUtility(IAuthenticationPolicy)
        req = Request.blank(self.host_url)
        creds = auth_policy.encode_mac_id(req, self.user_id)
        self.auth_token, self.auth_secret = creds

    def _cleanup_test_databases(self):
        # Don't cleanup databases unless we created them ourselves.
        if not self.distant:
            super(StorageFunctionalTestCase, self)._cleanup_test_databases()


MOCKMYID_PRIVATE_KEY = None
MOCKMYID_PRIVATE_KEY_DATA = {
    "algorithm": "DS",
    "x": "385cb3509f086e110c5e24bdd395a84b335a09ae",
    "y": "738ec929b559b604a232a9b55a5295afc368063bb9c20fac4e53a74970a4db795"
         "6d48e4c7ed523405f629b4cc83062f13029c4d615bbacb8b97f5e56f0c7ac9bc1"
         "d4e23809889fa061425c984061fca1826040c399715ce7ed385c4dd0d40225691"
         "2451e03452d3c961614eb458f188e3e8d2782916c43dbe2e571251ce38262",
    "p": "ff600483db6abfc5b45eab78594b3533d550d9f1bf2a992a7a8daa6dc34f8045a"
         "d4e6e0c429d334eeeaaefd7e23d4810be00e4cc1492cba325ba81ff2d5a5b305a"
         "8d17eb3bf4a06a349d392e00d329744a5179380344e82a18c47933438f891e22a"
         "eef812d69c8f75e326cb70ea000c3f776dfdbd604638c2ef717fc26d02e17",
    "q": "e21e04f911d1ed7991008ecaab3bf775984309c3",
    "g": "c52a4a0ff3b7e61fdf1867ce84138369a6154f4afa92966e3c827e25cfa6cf508b"
         "90e5de419e1337e07a2e9e2a3cd5dea704d175f8ebf6af397d69e110b96afb17c7"
         "a03259329e4829b0d03bbc7896b15b4ade53e130858cc34d96269aa89041f40913"
         "6c7242a38895c9d5bccad4f389af1d7a4bd1398bd072dffa896233397a",
}


def authenticate_to_token_server(url, email=None, audience=None):
    """Authenticate to the given token-server URL.

    This function generates a testing assertion for the specified email
    address, passes it to the specified token-server URL, and returns the
    resulting dict of authentication data.  It's useful for testing things
    that depend on having a live token-server.
    """
    # These modules are not (yet) hard dependencies of syncstorage,
    # so only import them is we really need them.
    global MOCKMYID_PRIVATE_KEY
    if MOCKMYID_PRIVATE_KEY is None:
        from browserid.jwt import DS128Key
        MOCKMYID_PRIVATE_KEY = DS128Key(MOCKMYID_PRIVATE_KEY_DATA)
    if email is None:
        email = "user_%s@mockmyid.com" % (random.randint(1, 100000),)
    if audience is None:
        audience = "https://persona.org"
    assertion = browserid.tests.support.make_assertion(
        email=email,
        audience=audience,
        issuer="mockmyid.com",
        issuer_keypair=(None, MOCKMYID_PRIVATE_KEY),
    )
    r = requests.get(url, headers={
        "Authorization": "Browser-ID " + assertion,
        "X-Conditions-Accepted": "true",
    })
    r.raise_for_status()
    creds = json.loads(r.content)
    for key in ("id", "key", "api_endpoint"):
        creds[key] = creds[key].encode("ascii")
    return creds


def run_live_functional_tests(TestCaseClass, argv=None):
    """Execute the given suite of testcases against a live server."""
    if argv is None:
        argv = sys.argv

    # This will only work using a StorageFunctionalTestCase subclass,
    # since we override the _authenticate() method.
    assert issubclass(TestCaseClass, StorageFunctionalTestCase)

    usage = "Usage: %prog [options] <server-url>"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-x", "--failfast", action="store_true",
                      help="stop after the first failed test")
    parser.add_option("", "--config-file",
                      help="name of the config file in use by the server")
    parser.add_option("", "--use-token-server", action="store_true",
                      help="the given URL is a tokenserver, not an endpoint")
    parser.add_option("", "--email",
                      help="email address to use for tokenserver tests")
    parser.add_option("", "--audience",
                      help="assertion audience to use for tokenserver tests")

    try:
        opts, args = parser.parse_args(argv)
    except SystemExit, e:
        return e.args[0]
    if len(args) != 2:
        parser.print_usage()
        return 2

    url = args[1]
    if opts.config_file is not None:
        os.environ["MOZSVC_TEST_INI_FILE"] = opts.config_file

    # If we're not using the tokenserver, the default implementation of
    # _authenticate will do just fine.
    if not opts.use_token_server:
        if opts.email is not None:
            msg = "cant specify email address unless using live tokenserver"
            raise ValueError(msg)
        if opts.audience is not None:
            msg = "cant specify audience unless using live tokenserver"
            raise ValueError(msg)
        os.environ["MOZSVC_TEST_REMOTE"] = url
        LiveTestCases = TestCaseClass

    # If we're using a live tokenserver, then we need to get some credentials
    # and an endpoint URL.
    else:
        creds = authenticate_to_token_server(url, opts.email, opts.audience)

        # Point the tests at the given endpoint URI, after stripping off
        # the trailing /2.0/UID component.
        host_url = urlparse.urlparse(creds["api_endpoint"])
        host_path = host_url.path.rstrip("/")
        host_path = "/".join(host_path.split("/")[:-2])
        host_url = host_url._replace(path=host_path)
        os.environ["MOZSVC_TEST_REMOTE"] = host_url.geturl()

        # Customize the tests to use the provisioned auth credentials.
        class LiveTestCases(TestCaseClass):
            def _authenticate(self):
                self.user_id = creds["uid"]
                self.auth_token = creds["id"].encode("ascii")
                self.auth_secret = creds["key"].encode("ascii")

    # Now use the unittest2 runner to execute them.
    suite = unittest2.TestSuite()
    suite.addTest(unittest2.makeSuite(LiveTestCases))
    runner = unittest2.TextTestRunner(
        stream=sys.stderr,
        failfast=opts.failfast,
    )
    res = runner.run(suite)
    if not res.wasSuccessful():
        return 1
    return 0


# Tell over-zealous test discovery frameworks that this isn't a real test.
run_live_functional_tests.__test__ = False

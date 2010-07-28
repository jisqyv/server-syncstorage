# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Sync Server
#
# The Initial Developer of the Original Code is the Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Tarek Ziade (tarek@mozilla.com)
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
"""
Basic tests to verify that the dispatching mechanism works.
"""
import base64
import json

from weave.server.tests.functional import support


class TestUser(support.TestWsgiApp):

    def setUp(self):
        super(TestUser, self).setUp()
        # user auth token
        environ = {'Authorization': 'Basic %s' % \
                        base64.encodestring('tarek:tarek')}
        self.app.extra_environ = environ

        # let's create some collections for our tests
        self.storage.set_user(1)

    def tearDown(self):
        # removing all data after the test
        self.storage.delete_user(1)
        super(TestUser, self).tearDown()

    def test_user_exists(self):
        res = self.app.get('/user/1.0/tarek')
        self.assertTrue(json.loads(res.body))

    def test_user_node(self):
        res = self.app.get('/user/1.0/tarek/node/weave')
        self.assertTrue(json.loads(res.body), 'http://localhost')

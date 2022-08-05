import argparse
import json
import os
import unittest
from urllib.parse import urlparse

from test.utils import HttpRequest
from servers.http import HTTPJsonServerFactory
from jsonroutes import JsonRoutes

class TestHTTPScript(unittest.TestCase):
    def setUp(self) -> None:
        routes = JsonRoutes(os.path.join(os.path.dirname(__file__), "fragments", "jsonroutes", "http_script.json"))
        self.factory = HTTPJsonServerFactory({}, routes, argparse.Namespace(files_root=os.path.join(os.path.dirname(__file__), "fragments", "scripts")))

    def make_request(self, uri):
        parsed_uri = urlparse(uri)
        req = HttpRequest(parsed_uri, [])

        child = self.factory.resource.getChild(parsed_uri.path[1:], req)
        req.write(child.render(req))

        return (req, b''.join(req.written), child)

    def test_basic(self):
        (req, _, _) = self.make_request("http://example.com/basic")
        self.assertEqual(req.responseCode, 200)

    def test_args(self):
        (req, _, _) = self.make_request("http://example.com/args")
        self.assertEqual(req.getResponseHeader("X-Args"), json.dumps(["arg1", "arg2"]))
        self.assertEqual(req.getResponseHeader("X-KWArgs"), json.dumps({"kwarg1" : "value1"}))
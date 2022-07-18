import argparse
import os
import unittest
from urllib.parse import urlparse

from twisted.web.test.requesthelper import DummyRequest

from servers.http import HTTPJsonServerFactory
from jsonroutes import JsonRoutes

class HttpRequest(DummyRequest):
    def __init__(self, parsed_uri, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self._serverName = parsed_uri.hostname.encode()
        self.uri = parsed_uri.path
        if len(parsed_uri.query):
            self.uri += "?" + parsed_uri.query
        self.uri = self.uri.encode()

    def isSecure(self):
        return self.uri.startswith(b'https')

class TestHTTP(unittest.TestCase):
    def setUp(self) -> None:
        routes = JsonRoutes(os.path.join(os.path.dirname(__file__), "fragments", "jsonroutes", "http.json"))
        self.factory = HTTPJsonServerFactory({}, routes, argparse.Namespace(files_root=os.path.join(os.path.dirname(__file__), "fragments", "files")))

    def make_request(self, uri):
        parsed_uri = urlparse(uri)
        req = HttpRequest(parsed_uri, [])
        child = self.factory.resource.getChild(parsed_uri.path[1:], req)
        body = child.render(req)

        return (req, body, child)

    def test_404(self):
        (req, _, _) = self.make_request("http://example.com/DoesNotExist")
        
        self.assertEqual(req.responseCode, 404)

    def test_file(self):
        (req, body, _) = self.make_request("http://example.com/index.html")
        
        self.assertEqual(req.responseCode, 200)
        self.assertEqual(body, b'Hello World')
        
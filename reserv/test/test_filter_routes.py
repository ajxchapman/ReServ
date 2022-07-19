import argparse
import os
import unittest

from jsonroutes import JsonRoutes
from servers.http import HTTPJsonServerFactory, HTTPException
from servers.dns import DNSJsonServerFactory, DNSException

class TestFilterRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.routes = JsonRoutes(os.path.join(os.path.dirname(__file__), "fragments", "jsonroutes", "filter.json"))

    def test_http(self):
        f = HTTPJsonServerFactory({}, self.routes, argparse.Namespace(files_root=os.path.join(os.path.dirname(__file__), "fragments", "files")))
        route, match, _ = f.filter_routes("http://example.com/test")
        self.assertEqual(route["id"], 1)
        self.assertEqual(match, "http://example.com/test")
    

    def test_dns_A(self):
        f = DNSJsonServerFactory({}, self.routes, argparse.Namespace())
        route, match, _ = f.filter_routes("example.com")
        self.assertEqual(route["id"], 2)
        self.assertEqual(match, "example.com")

    def test_dns_AAAA(self):
        f = DNSJsonServerFactory({}, self.routes, argparse.Namespace())
        route, match, _ = f.filter_routes("example.com", qtype="AAAA")
        self.assertEqual(route["id"], 3)
        self.assertEqual(match, "example.com")

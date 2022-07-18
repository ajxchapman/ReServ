import os
import unittest

from jsonroutes import JsonRoutes
from servers.http import HTTPJsonServerFactory, HTTPException
from servers.dns import DNSJsonServerFactory, DNSException

class TestFilterRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.routes = JsonRoutes(os.path.join(os.path.dirname(__file__), "fragments", "jsonroutes", "filter.json"))

    def test_http(self):
        f = HTTPJsonServerFactory({}, self.routes, os.path.join(os.path.dirname(__file__), "fragments", "wwwroot"))
        route, match, _ = f.filter_routes("http://example.com/test")
        self.assertEqual(route["id"], 1)
        self.assertEqual(match, "http://example.com/test")
    
    def test_http_exception(self):
        f = HTTPJsonServerFactory({}, self.routes, os.path.join(os.path.dirname(__file__), "fragments", "wwwroot"))

        with self.assertRaises(HTTPException):
            f.filter_routes("dns://example.com")

    def test_dns_A(self):
        f = DNSJsonServerFactory({}, self.routes)
        route, match, _ = f.filter_routes("dns://example.com")
        self.assertEqual(route["id"], 2)
        self.assertEqual(match, "example.com")

    def test_dns_AAAA(self):
        f = DNSJsonServerFactory({}, self.routes)
        route, match, _ = f.filter_routes("dns://example.com?type=AAAA")
        self.assertEqual(route["id"], 3)
        self.assertEqual(match, "example.com")

    def test_dns_exception(self):
        f = DNSJsonServerFactory({}, self.routes)

        with self.assertRaises(DNSException):
            f.filter_routes("http://example.com")
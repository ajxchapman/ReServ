import sys
import unittest

from twisted.names import dns

import src.servers.dns

replacements = {
    "ipv4_address" : "127.0.0.1",
    "ipv6_address" : "::1"
}

class TestJsonRoutes(unittest.TestCase):
    def test_normalise_A_default(self):
        results = src.servers.dns.normalise_response(
            replacements, 
            ".*\.example.com", 
            "test.example.com", 
            dns.Record_A, 
            "127.0.0.1"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_A.TYPE)
        self.assertEqual(results[0].dottedQuad(), "127.0.0.1")

    def test_normalise_A_args(self):
        results = src.servers.dns.normalise_response(
            replacements, 
            ".*\.example.com", 
            "test.example.com", 
            dns.Record_A, 
            {"address" : "127.0.0.1"}
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_A.TYPE)
        self.assertEqual(results[0].dottedQuad(), "127.0.0.1")

    def test_normalise_AAAA(self):
        results = src.servers.dns.normalise_response(
            replacements, 
            ".*\.example.com", 
            "test.example.com", 
            dns.Record_AAAA, 
            "::1"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_AAAA.TYPE)
        self.assertEqual(results[0].address, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01')

    def test_normalise_AAAA_args(self):
        results = src.servers.dns.normalise_response(
            replacements, 
            ".*\.example.com", 
            "test.example.com", 
            dns.Record_AAAA, 
            {"address" : "::1"}
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_AAAA.TYPE)
        self.assertEqual(results[0].address, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01')

    def test_normalise_replace(self):
        results = src.servers.dns.normalise_response(
            replacements, 
            ".*\.example.com", 
            "test.example.com", 
            dns.Record_A, 
            "{{ipv4_address}}"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_A.TYPE)
        self.assertEqual(results[0].dottedQuad(), "127.0.0.1")

    def test_normalise_replace_match(self):
        results = src.servers.dns.normalise_response(
            replacements, 
            "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?).example.com", 
            "127.0.0.1.example.com", 
            dns.Record_A, 
            "$1.$2.$3.$4"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_A.TYPE)
        self.assertEqual(results[0].dottedQuad(), "127.0.0.1")

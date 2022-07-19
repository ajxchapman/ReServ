import unittest

from twisted.names import dns

from servers.dns import normalise_response

replacements = {
    "ipv4_address" : "127.0.0.1",
    "ipv6_address" : "::1"
}

class TestDNSNormalise(unittest.TestCase):
    def test_normalise_A_default(self):
        results = normalise_response(
            replacements, 
            dns.Record_A, 
            "127.0.0.1"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_A.TYPE)
        self.assertEqual(results[0].dottedQuad(), "127.0.0.1")

    def test_normalise_A_args(self):
        results = normalise_response(
            replacements, 
            dns.Record_A, 
            {"address" : "127.0.0.1"}
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_A.TYPE)
        self.assertEqual(results[0].dottedQuad(), "127.0.0.1")

    def test_normalise_AAAA(self):
        results = normalise_response(
            replacements, 
            dns.Record_AAAA, 
            "::1"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_AAAA.TYPE)
        self.assertEqual(results[0].address, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01')

    def test_normalise_AAAA_args(self):
        results = normalise_response(
            replacements, 
            dns.Record_AAAA, 
            {"address" : "::1"}
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_AAAA.TYPE)
        self.assertEqual(results[0].address, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01')

    def test_normalise_replace(self):
        results = normalise_response(
            replacements, 
            dns.Record_A, 
            "{{ipv4_address}}"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_A.TYPE)
        self.assertEqual(results[0].dottedQuad(), "127.0.0.1")

    def test_normalise_replace_match(self):
        results = normalise_response(
            {**replacements, "1" : "127", "2" : "0", "3" : "0", "4" : "1"},
            dns.Record_A, 
            "$1.$2.$3.$4"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].TYPE, dns.Record_A.TYPE)
        self.assertEqual(results[0].dottedQuad(), "127.0.0.1")
import os
import ipaddress
import time
import unittest

from twisted.names import dns

from servers.dns import DNSJsonServerFactory
from jsonroutes import JsonRoutes

class NoopProtocol:
    def writeMessage(self, *args, **kwargs):
        self.answers = args[0].answers

class TestDNS(unittest.TestCase):
    def setUp(self) -> None:
        routes = JsonRoutes(os.path.join(os.path.dirname(__file__), "fragments", "jsonroutes", "dns.json"))
        self.factory = DNSJsonServerFactory({}, routes)

    def sendMessage(self, message):
        protocol = NoopProtocol()
        message.timeReceived = time.time()
        self.factory.handleQuery(message, protocol, None)
        return list(protocol.answers)

    def test_A(self):
        message = dns.Message()
        message.addQuery(b"a.example.com", type=dns.Record_A.TYPE)
        answ = self.sendMessage(message)

        self.assertEqual(answ[0].payload.TYPE, dns.Record_A.TYPE)
        self.assertEqual(ipaddress.ip_address(answ[0].payload.address), ipaddress.ip_address("127.0.0.1"))

    def test_AAAA(self):
        message = dns.Message()
        message.addQuery(b"aaaa.example.com", type=dns.Record_AAAA.TYPE)
        answ = self.sendMessage(message)

        self.assertEqual(answ[0].payload.TYPE, dns.Record_AAAA.TYPE)
        self.assertEqual(ipaddress.ip_address(answ[0].payload.address), ipaddress.ip_address("::1"))

    def test_A_CNAME(self):
        message = dns.Message()
        message.addQuery(b"acname.example.com", type=dns.Record_A.TYPE)
        answ = self.sendMessage(message)

        self.assertEqual(answ[0].payload.TYPE, dns.Record_CNAME.TYPE)
        self.assertEqual(str(answ[0].payload.name), "example.com")

    def test_TXT(self):
        message = dns.Message()
        message.addQuery(b"txt.example.com", type=dns.Record_TXT.TYPE)
        answ = self.sendMessage(message)

        self.assertEqual(answ[0].payload.TYPE, dns.Record_TXT.TYPE)
        self.assertListEqual(answ[0].payload.data, [b'Data1', b'Data2'])

    def test_MX(self):
        message = dns.Message()
        message.addQuery(b"mx.example.com", type=dns.Record_MX.TYPE)
        answ = self.sendMessage(message)

        self.assertEqual(answ[0].payload.TYPE, dns.Record_MX.TYPE)
        self.assertEqual(answ[0].payload.preference, 10)
        self.assertEqual(str(answ[0].payload.name), "mail.example.com")
import logging

from twisted.internet import reactor
from twisted.names import dns

import servers.dns
import servers.http

logger = logging.getLogger()

logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

if __name__ == "__main__":
    dns_server_factory = servers.dns.DNSJsonServerFactory()
    reactor.listenUDP(53, dns.DNSDatagramProtocol(dns_server_factory), interface="0.0.0.0")
    reactor.listenTCP(53, dns_server_factory, interface="0.0.0.0")

    http_resource = servers.http.HTTPJsonResource()
    reactor.listenTCP(80, servers.http.HTTPSite(http_resource), interface="0.0.0.0")
    reactor.listenSSL(443, servers.http.HTTPSite(http_resource), servers.http.SSLContextFactory(), interface="0.0.0.0")
    reactor.run()

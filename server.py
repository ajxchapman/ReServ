import logging
import logging.handlers
import os

from twisted.internet import reactor
from twisted.names import dns

import servers.dns
import servers.http

logger = logging.getLogger()

logger.setLevel(logging.DEBUG)
simple_formatter = logging.Formatter("%(levelname)s - %(message)s")
verbose_formatter = logging.Formatter("%(asctime)s [%(levelname)s] <%(module)s>: %(message)s")
stdout_handler = logging.StreamHandler()
stdout_handler.setLevel(logging.INFO)
stdout_handler.setFormatter(simple_formatter)
file_handler = logging.handlers.TimedRotatingFileHandler(os.path.join("files", "logs", "server.log"), when='D', interval=1, utc=True)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(verbose_formatter)
logger.addHandler(stdout_handler)
logger.addHandler(file_handler)


if __name__ == "__main__":
    dns_server_factory = servers.dns.DNSJsonServerFactory("example.com")
    reactor.listenUDP(53, dns.DNSDatagramProtocol(dns_server_factory), interface="0.0.0.0")
    reactor.listenTCP(53, dns_server_factory, interface="0.0.0.0")

    http_resource = servers.http.HTTPJsonResource()
    reactor.listenTCP(80, servers.http.HTTPSite(http_resource), interface="0.0.0.0")
    reactor.listenSSL(443, servers.http.HTTPSite(http_resource), servers.http.SSLContextFactory(), interface="0.0.0.0")
    reactor.run()

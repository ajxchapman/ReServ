import logging
import logging.handlers
import os
import sys
import argparse

from twisted.internet import reactor
from twisted.names import dns

import servers.dns
import servers.http

# Make sure our working directory is sane
os.chdir(os.path.split(os.path.abspath(__file__))[0])
logger = logging.getLogger()

# Setup logginer
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
    parser = argparse.ArgumentParser(description="research servers")
    parser.add_argument("domain_name", type=str,
                        help="the root domain name for the DNS server")

    args = parser.parse_args()

    dns_server_factory = servers.dns.DNSJsonServerFactory(args.domain_name)
    reactor.listenUDP(53, dns.DNSDatagramProtocol(dns_server_factory), interface="0.0.0.0")
    reactor.listenTCP(53, dns_server_factory, interface="0.0.0.0")

    http_resource = servers.http.HTTPJsonResource()
    reactor.listenTCP(80, servers.http.HTTPSite(http_resource), interface="0.0.0.0")
    reactor.listenSSL(443, servers.http.HTTPSite(http_resource), servers.http.SSLContextFactory(), interface="0.0.0.0")
    reactor.run()

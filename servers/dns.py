import logging

from twisted.names import dns, server

import clients.dns

logger = logging.getLogger()

class DNSJsonServerFactory(server.DNSServerFactory):
    noisy = False

    def __init__(self, *args, **kwargs):
        dns_client = clients.dns.DNSJsonClient()
        super().__init__(*args, clients=[dns_client], **kwargs)

    def handleQuery(self, message, protocol, address):
        logger.info("DNS: {} - {}".format(str(message.queries[0]), address[0] if address is not None else ""))
        return super().handleQuery(message, protocol, address)

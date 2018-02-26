import logging
import os

from twisted.names import dns, server

from jsonroutes import JsonRoutes
from utils import apply_middlewares
import clients.dns

logger = logging.getLogger()

class DNSJsonServerFactory(server.DNSServerFactory):
    noisy = False

    def __init__(self, domain, *args, **kwargs):
        self.middlewares = JsonRoutes(os.path.join("files", "middlewares", "dns_*.json"), key=lambda x: "default" in x, domain=domain)
        dns_client = clients.dns.DNSJsonClient()
        super().__init__(*args, clients=[dns_client], **kwargs)

    def handleQuery(self, message, protocol, address):
        _super = super()
        def _handleQuery(mpa):
            message, protocol, address = mpa
            return _super.handleQuery(message, protocol, address)

        name = message.queries[0].name.name.decode("UTF-8")
        logger.info("DNS: {} - {}".format(name, address[0] if address is not None else ""))

        return apply_middlewares(self.middlewares, name, _handleQuery)((message, protocol, address))

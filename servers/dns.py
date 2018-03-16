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
        self.middlewares = JsonRoutes(protocol="dns_middleware")
        dns_client = clients.dns.DNSJsonClient(domain)
        super().__init__(*args, clients=[dns_client], **kwargs)

    def sendReply(self, protocol, message, address):
        r_addr, r_port = address if address is not None else ("N/A", 0)
        if len(message.answers):
            for answer in message.answers:
                r_name = answer.name.name.decode("UTF-8")
                r_type = dns.QUERY_TYPES.get(answer.type, "UnknownType")
                r_answer = str(answer.payload)

                logger.info("DNS: [{client:s}] - {query:s} {type:s} {answer:s}".format(client=r_addr, query=r_name, type=r_type, answer=r_answer))
        else:
            for query in message.queries:
                r_name = query.name.name.decode("UTF-8")
                r_type = dns.QUERY_TYPES.get(query.type, "UnknownType")

                logger.info("DNS: [{client:s}] - {query:s} {type:s} -".format(client=r_addr, query=r_name, type=r_type))

        super().sendReply(protocol, message, address)

    def handleQuery(self, message, protocol, address):
        _super = super()
        def _handleQuery(mpa):
            message, protocol, address = mpa
            return _super.handleQuery(message, protocol, address)

        name = message.queries[0].name.name.decode("UTF-8")
        return apply_middlewares(self.middlewares.get_descriptors(name), _handleQuery)((message, protocol, address))

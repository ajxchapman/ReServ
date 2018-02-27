import logging
import os
import re

from twisted.internet import reactor
from twisted.names import dns, client

from jsonroutes import JsonRoutes
from utils import get_ipv4_address, get_ipv6_address

logger = logging.getLogger()

class DNSJsonClient(client.Resolver):
    """
    DNS resolver which responds to dns queries based on a JsonRoutes object
    """

    noisy = False

    def __init__(self, domain, ipv4_address=None, ipv6_address=None):
        self.domain = domain
        self.ipv4_address = ipv4_address or get_ipv4_address()
        self.ipv6_address = ipv6_address or get_ipv6_address()
        self.routes = JsonRoutes(os.path.join("files", "routes", "dns_*.json"), domain=self.domain)
        super().__init__(servers=[("8.8.8.8", 53)])

    def _lookup(self, lookup_name, lookup_cls, lookup_type, timeout):
        record = None
        record_type = None

        str_lookup_name = lookup_name.decode("UTF-8").lower()

        # Access route_descriptors directly to perform complex filtering
        for route_descriptor in self.routes.route_descriptors:
            if re.fullmatch(route_descriptor["route"], str_lookup_name):
                if lookup_cls == route_descriptor.get("class", dns.IN):
                    # Convert the route_descriptor type to an integer
                    rd_type = route_descriptor.get("type", "A")
                    if rd_type.isdigit():
                        rd_type = int(rd_typ)
                        rd_type_name = dns.QUERY_TYPES.get(rd_type, "UnknownType")
                    else:
                        rd_type_name = rd_type
                        rd_type = dns.REV_TYPES.get(rd_type_name, 0)

                    if lookup_type == rd_type:
                        logger.debug("Matched route {}".format(repr(route_descriptor)))

                        if "response" in route_descriptor:
                            response = re.sub(route_descriptor["route"], route_descriptor["response"], str_lookup_name).format(domain=self.domain, ipv4=self.ipv4_address, ipv6=self.ipv6_address)
                        else:
                            response = self.ipv6_address if rd_type_name == "AAAA" else self.ipv6_address

                        response = response.encode("UTF-8")
                        ttl = int(route_descriptor.get("ttl", "60"))
                        if "record" in route_descriptor:

                            logger.info(response)
                            record = getattr(dns, "Record_" + route_descriptor["record"], dns.UnknownRecord)(response, ttl=ttl)
                            record_type = dns.REV_TYPES.get(route_descriptor["record"], 0)
                        else:
                            record = getattr(dns, "Record_" + rd_type_name, dns.UnknownRecord)(response, ttl=ttl)
                            record_type = lookup_type
                        break

        if record is not None:
            try:
                return [(dns.RRHeader(lookup_name, record_type, lookup_cls, ttl, record),) ,(), ()]
            except:
                logger.exception("Unhandled exception with response")
        return [(), (), ()]

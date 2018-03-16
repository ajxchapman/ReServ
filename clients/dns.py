import logging
import os
import re

from twisted.internet import reactor
from twisted.names import dns, client

from jsonroutes import JsonRoutes
from utils import get_ipv4_address, get_ipv6_address, exec_cached_script

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
        self.routes = JsonRoutes(protocol="dns", domain=self.domain)
        self.replace_args = {"domain": self.domain, "ipv4": self.ipv4_address, "ipv6": self.ipv6_address}
        super().__init__(servers=[("8.8.8.8", 53)])

    def _lookup(self, lookup_name, lookup_cls, lookup_type, timeout):
        records = []
        record_type = None

        str_lookup_name = lookup_name.decode("UTF-8").lower()

        # Access route_descriptors directly to perform complex filtering
        for route_descriptor in self.routes.route_descriptors:
            if re.search(route_descriptor["route"], str_lookup_name):
                if lookup_cls == route_descriptor.get("class", dns.IN):

                    # Convert the route_descriptor type to an integer
                    rd_type = route_descriptor.get("type", str(lookup_type))
                    if rd_type.isdigit():
                        rd_type = int(rd_type)
                        rd_type_name = dns.QUERY_TYPES.get(rd_type, "UnknownType")
                    else:
                        rd_type_name = rd_type
                        rd_type = dns.REV_TYPES.get(rd_type_name, 0)

                    # If the lookup type matches the reoute descriptor type
                    if lookup_type == rd_type:
                        logger.debug("Matched route {}".format(repr(route_descriptor)))
                        ttl = int(route_descriptor.get("ttl", "60"))

                        # Obtain an array of responses
                        responses = [self.ipv6_address if rd_type_name == "AAAA" else self.ipv4_address]
                        if "response" in route_descriptor:
                            responses = route_descriptor["response"]
                        elif "script" in route_descriptor:
                            try:
                                args = route_descriptor.get("args", [])
                                kwargs = route_descriptor.get("kwargs", {})
                                get_record = exec_cached_script(route_descriptor["script"])["get_record"]
                                responses = get_record(lookup_name, lookup_cls, lookup_type, *args, **kwargs)
                            except Exception as e:
                                logger.exception("Error executing script {}".format(route_descriptor["script"]))

                        if isinstance(responses, str):
                            responses = [responses]

                        # Determine the record type and record type class
                        if "record" in route_descriptor:
                            record_type = dns.REV_TYPES.get(route_descriptor["record"], 0)
                            record_class = getattr(dns, "Record_" + route_descriptor["record"], dns.UnknownRecord)
                        else:
                            record_type = lookup_type
                            record_class = getattr(dns, "Record_" + rd_type_name, dns.UnknownRecord)

                        for response in responses:
                            # Replace regex groups in the route path
                            for i, group in enumerate(re.search(route_descriptor["route"], str_lookup_name).groups()):
                                if group is not None:
                                    response = response.replace("${}".format(i + 1), group)
                            response = response.format(**self.replace_args).encode()
                            records.append((lookup_name, record_type, lookup_cls, ttl, record_class(response, ttl=ttl)))
                        break

        if len(records):
            try:
                return [tuple([dns.RRHeader(*x) for x in records]) ,(), ()]
            except:
                logger.exception("Unhandled exception with response")
        return [(), (), ()]

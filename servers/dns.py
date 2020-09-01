import inspect
import logging
import os
import random
import re

from twisted.names import dns, server

from jsonroutes import JsonRoutes
import utils

logger = logging.getLogger()

# Shim classes for DNS records that twisted does not support
record_classes = {k.split("_", 1)[1] : v for k,v in inspect.getmembers(dns, lambda x: inspect.isclass(x) and x.__name__.startswith("Record_"))}

class Record_CAA:
    """
    The Certification Authority Authorization record.
    """
    TYPE = 257
    fancybasename = 'CAA'

    def __init__(self, record, ttl=None):
        record = record.split(b' ', 2)
        self.flags = int(record[0])
        self.tag = record[1]
        self.value = record[2].replace(b'"', b'')
        self.ttl = dns.str2time(ttl)

    def encode(self, strio, compDict = None):
        strio.write(bytes([self.flags, len(self.tag)]))
        strio.write(self.tag)
        strio.write(self.value)

    def decode(self, strio, length = None):
        pass

    def __hash__(self):
        return hash(self.address)

    def __str__(self):
        return '<CAA record=%d %s "%s" ttl=%s>' % (self.flags, self.tag.decode(), self.value.decode(), self.ttl)
    __repr__ = __str__

# Add CAA Type to the DNS Query and Reverse types lists
dns.QUERY_TYPES[Record_CAA.TYPE] = Record_CAA.fancybasename
dns.REV_TYPES[Record_CAA.fancybasename] = Record_CAA.TYPE
record_classes[Record_CAA.fancybasename] = Record_CAA

class DNSJsonServerFactory(server.DNSServerFactory):
    noisy = False

    def __init__(self, *args, **kwargs):
        self.routes = utils.get_routes()
        self.ipv4_address = utils.get_variables().get("ipv4_address", utils.get_ipv4_address())
        self.ipv6_address = utils.get_variables().get("ipv6_address", utils.get_ipv6_address())
        
        super().__init__(*args, **kwargs)

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

    def _lookup(self, route_descriptor, qname, lookup_cls, qtype, timeout):
        records = []
        record_type = None

        # Return an empty response if no route descriptor is found
        if len(route_descriptor) == 0:
            return [(), (), ()]

        # Convert the route_descriptor type to an integer
        rd_type = route_descriptor.get("type", str(qtype))
        if rd_type.isdigit():
            rd_type = int(rd_type)
            rd_type_name = dns.QUERY_TYPES.get(rd_type, "UnknownType")
        else:
            rd_type_name = rd_type
            rd_type = dns.REV_TYPES.get(rd_type_name, 0)

        ttl = int(route_descriptor.get("ttl", "60"))
        record_type = qtype
        record_class = record_classes.get(rd_type_name, dns.UnknownRecord)

        # Determine the record type and record type class
        if "record" in route_descriptor:
            record_type = dns.REV_TYPES.get(route_descriptor["record"], 0)
            record_class = record_classes.get(route_descriptor["record"], dns.UnknownRecord)

        # Obtain an array of responses
        responses = [self.ipv6_address if rd_type_name == "AAAA" else self.ipv4_address]
        if "response" in route_descriptor:
            responses = route_descriptor["response"]

        if "script" in route_descriptor:
            try:
                args = route_descriptor.get("args", [])
                kwargs = route_descriptor.get("kwargs", {})
                get_record = utils.exec_cached_script(route_descriptor["script"])["get_record"]
                responses = get_record(qname, lookup_cls, qtype, *args, **kwargs)
            except:
                logger.exception("Error executing script {}".format(route_descriptor["script"]))

        # Coerce the response into a list
        if isinstance(responses, str):
            responses = [responses]
        for response in responses if not route_descriptor.get("random", False) else [random.choice(responses)]:
            # Replace regex groups in the route path
            for i, group in enumerate(re.search(route_descriptor["route"], qname).groups()):
                if group is not None:
                    response = response.replace("${}".format(i + 1), group)
            
            # Allow for dynamic routes, e.g. returned by scripts, to include variables
            response = self.routes.replace_variables(response).encode()
            records.append((qname, record_type, lookup_cls, ttl, record_class(response, ttl=ttl)))

        if len(records):
            try:
                return [tuple([dns.RRHeader(*x) for x in records]) ,(), ()]
            except:
                logger.exception("Unhandled exception with response")
        return [(), (), ()]

    def handleQuery(self, message, protocol, address):
        query = message.queries[0]

        # Standardise the query name
        qname = query.name.name
        if not isinstance(qname, str):
            qname = qname.decode('idna')
        qname = qname.lower()

        # At this point we only know of dns.IN lookup classes
        lookup_cls = dns.IN

        def _handleQuery(route_descriptor, qname, lookup_cls, qtype, message, protocol, address):
            self.gotResolverResponse(self._lookup(route_descriptor, qname, lookup_cls, qtype, 1000), protocol, message, address)

        # Access route_descriptors directly to perform complex filtering
        route_descriptor = {}
        for _route_descriptor, _ in self.routes.get_descriptors(qname, rfilter=lambda x: x.get("protocol") == "dns"):
            if lookup_cls == _route_descriptor.get("class", dns.IN):

                # Convert the route_descriptor type to an integer
                rd_type = _route_descriptor.get("type", query.type)
                if not isinstance(rd_type, int):
                    rd_type = dns.REV_TYPES.get(rd_type, 0)

                # If the lookup type matches the route_descriptor type
                if query.type == rd_type:
                    logger.debug("Matched route {}".format(repr(_route_descriptor)))
                    route_descriptor = _route_descriptor
                    break

        middlewares = self.routes.get_descriptors(qname, rfilter=lambda x: x.get("protocol") == "dns_middleware")
        return utils.apply_middlewares(middlewares, _handleQuery)(route_descriptor, qname, lookup_cls, query.type, message, protocol, address)

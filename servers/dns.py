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

    def _lookup(self, route_descriptor, qname, lookup_cls, qtype, timeout):
        records = []
        record_type = None

        # Return an empty response if no route descriptor is found
        action_des = route_descriptor.get("action")
        if action_des is None:
            return [(), (), ()]

        # Convert the type to an integer
        rd_type = action_des.get("type", str(qtype))
        if rd_type.isdigit():
            rd_type = int(rd_type)
            rd_type_name = dns.QUERY_TYPES.get(rd_type, "UnknownType")
        else:
            rd_type_name = rd_type
            rd_type = dns.REV_TYPES.get(rd_type_name, 0)

        ttl = int(action_des.get("ttl", "60"))
        record_type = qtype
        record_class = record_classes.get(rd_type_name, dns.UnknownRecord)

        # Determine the record type and record type class
        if "record" in action_des:
            record_type = dns.REV_TYPES.get(action_des["record"], 0)
            record_class = record_classes.get(action_des["record"], dns.UnknownRecord)

        # Obtain an array of responses
        responses = [self.ipv6_address if rd_type_name == "AAAA" else self.ipv4_address]
        if "response" in action_des:
            responses = action_des["response"]

        if "script" in action_des:
            try:
                args = action_des.get("args", [])
                kwargs = action_des.get("kwargs", {})
                get_record = utils.exec_cached_script(action_des["script"])["get_record"]
                responses = get_record(qname, lookup_cls, qtype, *args, **kwargs)
            except:
                logger.exception("Error executing script {}".format(action_des["script"]))

        # Coerce the response into a list
        if isinstance(responses, str):
            responses = [responses]
        for response in responses if not action_des.get("random", False) else [random.choice(responses)]:
            # Replace regex groups in the route path
            for i, group in enumerate(re.search(route_descriptor["route"], qname).groups()):
                if group is not None:
                    response = response.replace("${}".format(i + 1), group)
            
            # Allow for dynamic routes, e.g. returned by scripts, to include variables
            response = self.routes.replace_variables(response).encode()
            records.append(dict(
                name=qname, 
                type=record_type, 
                cls=lookup_cls, 
                ttl=ttl, 
                payload=record_class(response, ttl=ttl), 
                auth=True
            ))

        if len(records):
            try:
                return [tuple([dns.RRHeader(**x) for x in records]) ,(), ()]
            except:
                logger.exception("Unhandled exception with response")
        return [(), (), ()]

    def handleQuery(self, message, protocol, address):
        def _handleQuery(route_descriptor, qname, lookup_cls, qtype, message, protocol, address):
            return self._lookup(route_descriptor, qname, lookup_cls, qtype, 1000)

        query = message.queries[0]

        # Standardise the query name
        qname = query.name.name
        if not isinstance(qname, str):
            qname = qname.decode('idna')
        qname = qname.lower()

        # At this point we only know of dns.IN lookup classes
        lookup_cls = dns.IN

        # Access route_descriptors directly to perform complex filtering
        route_descriptor = {}
        for _route_descriptor, _ in self.routes.get_descriptors(qname, rfilter=lambda x: x.get("protocol") == "dns"):
            _action_des = _route_descriptor.get("action")
            if _action_des is None:
                continue

            if lookup_cls == _action_des.get("class", dns.IN):

                # Convert the route_descriptor type to an integer
                rd_type = _action_des.get("type", query.type)
                if not isinstance(rd_type, int):
                    rd_type = dns.REV_TYPES.get(rd_type, 0)

                # If the lookup type matches the route_descriptor type
                if query.type == rd_type:
                    route_descriptor = _route_descriptor
                    break

        middlewares = self.routes.get_descriptors(qname, rfilter=lambda x: x.get("protocol") == "dns_middleware")
        response = utils.apply_middlewares(middlewares, _handleQuery)(route_descriptor, qname, lookup_cls, query.type, message, protocol, address)
        self.gotResolverResponse(response, protocol, message, address)

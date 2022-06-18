import inspect
import logging
import random
import re


from twisted.names import dns, server

import utils

logger = logging.getLogger()

class Record_CAA:
    """
    The Certification Authority Authorization record.
    """
    TYPE = 257
    fancybasename = 'CAA'

    def __init__(self, data=b'', ttl=None):
        record = data.split(b' ', 2)
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

# Shim classes for DNS records that twisted does not support
record_classes = {k.split("_", 1)[1] : v for k,v in inspect.getmembers(dns, lambda x: inspect.isclass(x) and x.__name__.startswith("Record_"))}
record_classes[Record_CAA.fancybasename] = Record_CAA
record_signatures = {
    dns.Record_A.TYPE : ("address", {"address" : bytes, "ttl" : int}, []),
    dns.Record_AAAA.TYPE : ("address", {"address" : bytes, "ttl" : int}, []),
    dns.Record_SOA.TYPE : (None, {"mname": bytes, "rname" : bytes, "serial" : int, "refresh" : int, "retry" : int, "expire" : int, "minimum" : int, "ttl" : int}, []),
    dns.Record_SRV.TYPE : (None, {"priority" : int, "weight" : int, "port" : int, "target" : bytes, "ttl" : int}, []),
    dns.Record_MX.TYPE : ("name", {"preference" : int, "name" : bytes, "ttl" : int}, []),
    dns.Record_TXT.TYPE : ("data", {"data" : bytes, "ttl" : int}, ["data"]),
    dns.Record_SPF.TYPE : ("data", {"data" : bytes, "ttl" : int}, ["data"]),
    Record_CAA.TYPE : ("data", {"data" : bytes, "ttl" : int}, []),
    -1 : ("name", {"name" : bytes, "ttl" : int}, []), # Catch-All
}

def normalise_response(replacements, route, query, record_class, responses):
    default, arg_types, varargs = record_signatures.get(record_class.TYPE, record_signatures[-1])

    # Coerce the response into a list
    if not isinstance(responses, list):
        responses = [responses]
    
    results = []
    for response in responses:
        # Coerce kwargs into a dict
        kwargs = response
        if not isinstance(response, dict):
            if default is None:
                raise Exception(f"Record {record_class.fancybasename} has no default")
            kwargs = {default : response}
       
        # Replace replacements and search groups in response
        kwargs = utils.replace_variables(kwargs, {**replacements, **{str(k): v for k, v in enumerate(re.search(route, query).groups(), 1)}})

        # Cast response kwargs to correct types
        for k in kwargs.keys():
            v = kwargs[k]
            if not isinstance(v, str):
                continue
            t = arg_types.get(k, str)
            if not isinstance(v, t):
                if t == bytes:
                    v = v.encode()
                elif t == int:
                    v = int(v)
                else:
                    raise Exception(f"Uncastable type {t}")
                kwargs[k] = v

        # Extract varargs
        args = []
        for vararg in varargs:
            args.append(kwargs[vararg])
            del kwargs[vararg]
        
        # Create the record object
        results.append(record_class(*args, **kwargs))
    return results

class DNSJsonServerFactory(server.DNSServerFactory):
    noisy = False

    def __init__(self, variables, routes, *args, **kwargs):
        self.variables = variables
        self.routes = routes
        self.ipv4_address = variables["ipv4_address"]
        self.ipv6_address = variables["ipv6_address"]

        super().__init__(*args, **kwargs)

    def _lookup(self, route_descriptor, qname, lookup_cls, qtype, timeout):
        answer = []
        authority = []
        additional = []

        action_descriptiors = route_descriptor.get("action", [])
        if isinstance(action_descriptiors, dict):
            action_descriptiors = [action_descriptiors]
        for action in action_descriptiors:
            # Convert the type to an integer
            rd_type = action.get("type", str(qtype))
            if rd_type.isdigit():
                rd_type = int(rd_type)
                rd_type_name = dns.QUERY_TYPES.get(rd_type, "UnknownType")
            else:
                rd_type_name = rd_type
                rd_type = dns.REV_TYPES.get(rd_type_name, 0)

            ttl = int(action.get("ttl", "60"))
            record_type = qtype
            record_class = record_classes.get(rd_type_name, dns.UnknownRecord)

            # Determine the record type and record type class
            if "record" in action:
                record_type = dns.REV_TYPES.get(action["record"], 0)
                record_class = record_classes.get(action["record"], dns.UnknownRecord)

            # Obtain an array of responses
            responses = [self.ipv6_address if rd_type_name == "AAAA" else self.ipv4_address]
            if "response" in action:
                responses = action["response"]

            if "script" in action:
                try:
                    args = action.get("args", [])
                    kwargs = action.get("kwargs", {})
                    get_record = utils.exec_cached_script(action["script"])["get_record"]
                    responses = get_record(qname, lookup_cls, qtype, *args, **kwargs)
                except:
                    logger.exception("Error executing script {}".format(action["script"]))

            # TODO: this bit
            responses = normalise_response(xxxxxxxxxxxx sdfg)
            for response in responses if not action.get("random", False) else [random.choice(responses)]:
                if response.ttl is None:
                    response.ttl = ttl

                record = dns.RRHeader(
                    name=qname,
                    type=record_type,
                    cls=lookup_cls,
                    ttl=ttl,
                    payload=response,
                    auth=action.get("authoritative", True)
                )

                if action.get("section") == "authority":
                    authority.append(record)
                elif action.get("section") == "additional":
                    additional.append(record)
                else:
                    answer.append(record)

        if len(answer + authority + additional):
            try:
                # answer, authority and additional sections
                return [tuple(answer) , tuple(authority), tuple(additional)]
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

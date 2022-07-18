import inspect
import logging
import random
import re
from urllib.parse import parse_qs, urlparse

from twisted.names import dns, server

from jsonroutes import JsonRoutes
import utils as utils

logger = logging.getLogger()

class DNSException(Exception):
    pass

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
type_bytes = lambda x: x.encode()
type_bytearray = lambda x: [type_bytes(y) for y in (x if isinstance(x, list) else [x])]
record_classes = {k.split("_", 1)[1] : v for k,v in inspect.getmembers(dns, lambda x: inspect.isclass(x) and x.__name__.startswith("Record_"))}
record_classes[Record_CAA.fancybasename] = Record_CAA
record_signatures = {
    dns.Record_A.TYPE : ("address", {"address" : type_bytes, "ttl" : int}, []),
    dns.Record_AAAA.TYPE : ("address", {"address" : type_bytes, "ttl" : int}, []),
    dns.Record_SOA.TYPE : (None, {"mname": type_bytes, "rname" : type_bytes, "serial" : int, "refresh" : int, "retry" : int, "expire" : int, "minimum" : int, "ttl" : int}, []),
    dns.Record_SRV.TYPE : (None, {"priority" : int, "weight" : int, "port" : int, "target" : type_bytes, "ttl" : int}, []),
    dns.Record_MX.TYPE : ("name", {"preference" : int, "name" : type_bytes, "ttl" : int}, []),
    dns.Record_TXT.TYPE : ("data", {"data" : type_bytearray, "ttl" : int}, ["data"]),
    dns.Record_SPF.TYPE : ("data", {"data" : type_bytearray, "ttl" : int}, ["data"]),
    Record_CAA.TYPE : ("data", {"data" : type_bytes, "ttl" : int}, []),
    -1 : ("name", {"name" : type_bytes, "ttl" : int}, []), # Catch-All
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
                raise DNSException(f"Record {record_class.fancybasename} has no default")
            kwargs = {default : response}
       
        # Replace replacements and search groups in response
        kwargs = utils.replace_variables(kwargs, {**replacements, **{str(k): v for k, v in enumerate(re.search(route, query).groups(), 1)}})

        # Cast response kwargs to correct types
        for k in kwargs.keys():
            try:
                kwargs[k] = arg_types.get(k, str)(kwargs[k])
            except (ValueError, TypeError):
                raise DNSException(f"Uncastable type '{v}' for DNS {dns.QUERY_TYPES[record_class.TYPE]} response")

        # Extract varargs
        args = []
        for vararg in varargs:
            args.extend(kwargs[vararg])
            del kwargs[vararg]
        
        # Create the record object
        try:
            results.append(record_class(*args, **kwargs))
        except TypeError as e:
            # TODO: Add inspect.signature parsing here
            raise DNSException(f"Unknown argument to DNS {dns.QUERY_TYPES[record_class.TYPE]} response")
    return results

class DNSJsonServerFactory(server.DNSServerFactory):
    proto = "DNS"
    noisy = False

    def __init__(self, variables: dict, routes: JsonRoutes, opts: dict, *args, **kwargs):
        self.variables = variables
        self.routes = routes
        self.opts = opts

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
            

            # Determine the record type and record type class
            record_type = qtype
            record_class = record_classes.get(rd_type_name, dns.UnknownRecord)
            if "record" in action:
                record_type = dns.REV_TYPES.get(action["record"], 0)
                record_class = record_classes.get(action["record"], dns.UnknownRecord)

            # Obtain an array of responses
            responses = []
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

            responses = normalise_response(self.variables, route_descriptor["route"], qname, record_class, responses)
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

        route_descriptor, qname, middlewares = self.filter_routes(f"dns://{qname}?type={query.type}")
        response = utils.apply_middlewares(self.opts, middlewares, _handleQuery)(route_descriptor, qname, lookup_cls, query.type, message, protocol, address)
        self.gotResolverResponse(response, protocol, message, address)


    def filter_routes(self, uri):
        parsed_uri = urlparse(uri)
        parsed_qs = parse_qs(parsed_uri.query)
        if parsed_uri.scheme != "dns":
            raise DNSException(f"Unrecognised scheme '{parsed_uri.scheme}'")
        query_name = parsed_uri.hostname
        query_cls = int(parsed_qs.get("cls", [dns.IN])[0]) # default to dns.IN
        query_type = parsed_qs.get("type", [dns.Record_A.TYPE])[0] # default to dns.Record_A
        query_type = dns.REV_TYPES.get(query_type) or int(query_type)

        # Access route_descriptors directly to perform complex filtering
        route_descriptor = {}
        for _route_descriptor, _ in self.routes.get_descriptors(query_name, rfilter=lambda x: x.get("protocol") == "dns"):
            _action_des = _route_descriptor.get("action")
            if _action_des is None:
                continue

            if query_cls == _action_des.get("class", dns.IN):
                # Convert the route_descriptor type to an integer
                rd_type = _action_des.get("type", query_type)
                if not isinstance(rd_type, int):
                    rd_type = dns.REV_TYPES.get(rd_type, 0)

                # If the lookup type matches the route_descriptor type
                if query_type == rd_type:
                    route_descriptor = _route_descriptor
                    break

        middlewares = self.routes.get_descriptors(query_name, rfilter=lambda x: x.get("protocol") == "dns_middleware")
        return route_descriptor, query_name, middlewares
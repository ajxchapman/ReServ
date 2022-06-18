import datetime
import logging
import logging.handlers
import os
import string

from twisted.names import dns
from twisted.web import http

logger = logging.getLogger("server_log")

# Setup logger
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

printable_chars = set(bytes(string.printable, 'ascii'))
def printable(data):
    return all(x in printable_chars for x in data)

def http_log(next, route, match, request):
    def _log(result, timestamp, request, body):
        host = http._escape(request.getRequestHostname() or "-")
        referrer = http._escape(request.getHeader(b"referer") or "-")
        agent = http._escape(request.getHeader(b"user-agent") or "-")

        line = 'HTTP [{timestamp:s}]: "{ip:s}" - {scheme:s}://{host:s}:{port:d} "{method:s} {uri:s} {protocol:s}" {code:d} {length:s} "{referrer:s}" "{agent:s}"'
        line = line.format(
            ip=http._escape(request.getClientIP() or "-"),
            scheme="https" if request.isSecure() or request.host.port in [443, 8443] else "http",
            host=host,
            port=request.getHost().port,
            timestamp=timestamp,
            method=http._escape(request.method),
            uri=http._escape(request.uri),
            protocol=http._escape(request.clientproto),
            code=request.code,
            length=str(request.sentLength) or "-",
            referrer=referrer,
            agent=agent,
        )
        logger.info(line)

        if route.get("debug") == True:
            for k, v in request.requestHeaders.getAllRawHeaders():
                print(f"\t{k.decode()}: {', '.join([x.decode() for x in v])}")
            
            if body is not None:
                if printable(body):
                    print("\n\t" + "\n\t".join(body.decode("ascii").splitlines()))

    timestamp = datetime.datetime.now().isoformat()
    body = None
    if route.get("debug") == True:
        body = request.content.read(4069)
        request.content.seek(0)
    # Log after the request has finished so accurate response code and response length can be logged
    request.notifyFinish().addBoth(_log, timestamp, request, body)
    return next(route, match, request)

def dns_log(next, route, qname, lookup_cls, qtype, message, protocol, address):
    timestamp = datetime.datetime.now().isoformat()
    response = next(route, qname, lookup_cls, qtype, message, protocol, address)

    r_addr, r_port = address if address is not None else ("N/A", 0)
    answers = response[0]
    if len(answers):
        for answer in answers:
            r_name = answer.name.name.decode("UTF-8")
            r_type = dns.QUERY_TYPES.get(answer.type, "UnknownType")
            r_answer = str(answer.payload)

            logger.info(" DNS [{timestamp:s}]: \"{client:s}\" - {query:s} {type:s} {answer:s}".format(timestamp=timestamp, client=r_addr, query=r_name, type=r_type, answer=r_answer))
    else:
        for query in message.queries:
            r_name = query.name.name.decode("UTF-8")
            r_type = dns.QUERY_TYPES.get(query.type, "UnknownType")

            logger.info(" DNS [{timestamp:s}]: \"{client:s}\" - {query:s} {type:s} -".format(timestamp=timestamp, client=r_addr, query=r_name, type=r_type))

    return response

def ssl_log(next, server_name_indication, connection):
    timestamp = datetime.datetime.now().isoformat()
    logger.info(" SSL [{timestamp:s}]: {sni:s}".format(timestamp=timestamp, sni=server_name_indication))
    return next(server_name_indication, connection)
import json
import re

from twisted.internet import reactor, defer
from twisted.web.http_headers import Headers
from twisted.web.client import Agent
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

@implementer(IBodyProducer)
class BytesProducer(object):
    """
    Simple string body producer
    """

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

def send_webhook(url, data):
    if len(url):
        agent = Agent(reactor)
        headers = Headers()
        headers.addRawHeader("content-type", "application/json")

        agent.request(b"POST", url.encode(), headers, BytesProducer(json.dumps(data).encode()))

def should_alert(route, path):
    alert = False
    if "slack" in route:
        alert = bool(route["slack"])
        if isinstance(route["slack"], str):
            alert = re.search(route["slack"], path)
    return alert

def http_alert(next, route, route_match, request, message="HTTP Alert:\n{url} requested from {client}\n```\n{request}```", webhook=None, check_route=False):
    if check_route == False or should_alert(route, route_match):
        args = {}
        args["scheme"] = "https" if request.isSecure() else "http"
        args["host"] = request.getRequestHostname().decode("UTF-8") or "-"
        args["port"] = (":%d" % request.getHost().port) if request.getHost().port != {"http": 80, "https": 443}[args["scheme"]] else ""
        args["query_string"] = request.uri.decode("UTF-8")
        args["client"] = request.getClientIP()

        args["url"] = f'{args["scheme"]}://{args["host"]}{args["port"]}{args["query_string"]}'
        args["headers"] = "\n".join(f"{key.decode()}: {b', '.join(value).decode()}" for key, value in request.requestHeaders.getAllRawHeaders())
        args["request"] = f'{request.method.decode()} {args["query_string"]} {request.clientproto.decode()}\n{args["headers"]}'

        message = message.format(**args).strip()
        send_webhook(webhook, {"text" : message})
    return next(route, route_match, request)

def dns_alert(next, route, qname, lookup_cls, qtype, message, protocol, address, webhook=None):
    if should_alert(route, qname):
        send_webhook(webhook, {"text" : f"DNS Alert: {qname} request from {address[0]}"})
    return next(route, qname, lookup_cls, qtype, message, protocol, address)
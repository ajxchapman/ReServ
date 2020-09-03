import json
import re

from twisted.internet import reactor
from twisted.web.http_headers import Headers

import clients.http

def send_webhook(webhook, data):
    if len(webhook):
        agent = clients.http.HTTPJsonClient(reactor)
        headers = Headers()
        headers.addRawHeader("content-type", "application/json")
        
        agent.request("POST", webhook, headers=headers, bodyProducer=clients.http.StringProducer(json.dumps(data).encode()))

def should_alert(route, path):
    alert = False
    if "slack" in route:
        alert = bool(route["slack"])
        if isinstance(route["slack"], str):
            alert = re.search(route["slack"], path)
    return alert

def http_alert(next, route, route_match, request, webhook=None):
    if should_alert(route, route_match):
        scheme = "https" if request.isSecure() else "http"
        host = request.getRequestHostname().decode("UTF-8") or "-"
        port = (":%d" % request.getHost().port) if request.getHost().port != {"http": 80, "https": 443}[scheme] else ""
        query_string = request.uri.decode("UTF-8")
        client = request.getClientIP()

        url = f"{scheme}://{host}{port}{query_string}"
        header_text = "\n".join(f"{key.decode()}: {b', '.join(value).decode()}" for key, value in request.requestHeaders.getAllRawHeaders())
        request_text = f"{request.method.decode()} {query_string} {request.clientproto.decode()}\n{header_text}"
        
        message = f"HTTP Alert: {url} requested from {client}\n```\n{request_text}```"
        send_webhook(webhook, {"text" : message})
    return next(route, route_match, request)

def dns_alert(next, route, qname, lookup_cls, qtype, message, protocol, address, webhook=None):
    if should_alert(route, qname):
        send_webhook(webhook, {"text" : f"DNS Alert: {qname} request from {address[0]}"})
    return next(route, qname, lookup_cls, qtype, message, protocol, address)
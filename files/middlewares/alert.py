import logging
import re

from twisted.names import dns

logger = logging.getLogger()
tag_regex = re.compile("(?:^|\\.|\?|=|&|/)((?:[a-f0-9]{8}){1,2})(?:\\.|\?|=|&|/|$)", re.I)
tags = {}

HTTP_TAG_PATH_HEADLINE = "HTTP Path Tag Alert {}->'{}'"
HTTP_TAG_HOST_HEADLINE = "HTTP Host Tag Alert {}->'{}'"
HTTP_PATH_HEADLINE = "HTTP Path Alert {}->'{}'"
HTTP_REPORT = "    client: {}\n    url: {}\n    headers: \n        {}\n"

DNS_TAG_HEADLINE = "DNS Tag Alert {}->'{}'"
DNS_REPORT = "    client: {}\n    name: {}\n    type: {}"

SSL_TAG_HEADLINE = "SSL Tag SNI Alert '{}'"
SSL_REPORT = "    SNI: {}"


def generate_http_report(request, headline_template=HTTP_PATH_HEADLINE):
    client = (request.getClientIP() or "-")
    path = request.path.decode("UTF-8")
    url = request.uri.decode("UTF-8")
    headers = "\n        ".join(["{}: {}".format(x.decode(), b", ".join(y).decode()) for x,y in request.requestHeaders.getAllRawHeaders()])

    headline = headline_template.format(client, path)
    report = HTTP_REPORT.format(client, url, headers)
    return headline, report


def generate_dns_report(message, protocol, address):
    client = address[0] if address is not None else ""
    name = message.queries[0].name.name.decode("UTF-8")
    dnstype = dns.QUERY_TYPES.get(message.queries[0].type, "UnknownType")

    headline = DNS_TAG_HEADLINE.format(client, name)
    report = DNS_REPORT.format(client, name, dnstype)
    return headline, report


def generate_ssl_report(connection):
    server_name_indication = (connection.get_servername() or b'').decode("UTF-8")

    headline = SSL_TAG_HEADLINE.format(server_name_indication)
    report = SSL_REPORT.format(server_name_indication)
    return headline, report


def report_tag(tag, headline, detail):
    rep = "ALERT [{}]: {}\n{}".format(tag, headline, detail)
    logger.info(rep)


def http_alert_tag(request, next):
    path = request.uri.decode("UTF-8")
    match = tag_regex.search(path)
    if match is not None:
        headline, report = generate_http_report(request, headline_template=HTTP_TAG_PATH_HEADLINE)
        report_tag(match.group(1), headline, report)

    host = request.getRequestHostname().decode("UTF-8") or "-"
    match = tag_regex.search(host)
    if match is not None:
        headline, report = generate_http_report(request, headline_template=HTTP_TAG_HOST_HEADLINE)
        report_tag(match.group(1), headline, report)
    return next(request)


def dns_alert_tag(mpa, next):
    message, protocol, address = mpa
    name = message.queries[0].name.name.decode("UTF-8")

    match = tag_regex.search(name)
    if match is not None:
        headline, report = generate_dns_report(message, protocol, address)
        report_tag(match.group(1), headline, report)
    return next(mpa)


def ssl_alert_tag(connection, next):
    server_name_indication = (connection.get_servername() or b'').decode("UTF-8")

    match = tag_regex.search(server_name_indication)
    if match is not None:
        headline, report = generate_ssl_report(connection)
        report_tag(match.group(1), headline, report)
    return next(connection)

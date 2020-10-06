import os
import random
import sys
import time

from twisted.web.resource import Resource

rebind_mappings = {}

def find_file(request_path):
    search_paths = [
        os.path.abspath(os.path.dirname(__file__)),
        os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "files", "wwwroot"))
    ]

    for search_path in search_paths:
        html_path = os.path.abspath(os.path.join(search_path, "." + request_path))
        if os.path.isfile(html_path):
            if html_path.endswith(".html"):
                if html_path.startswith(search_path):
                    return html_path
    return None

class RebindPage(Resource):
    isLeaf = True

    def render_GET(self, request):
        scheme = "https" if request.isSecure() else "http"
        domain = request.getRequestHostname().decode()
        address = request.args.get(b'address', [b'127.0.0.1'])[0]

        port = request.args.get(b'port', [None])[0]
        # Remove port from hostname, record if required
        if b':' in request.getHeader(b'host'):
            _port = request.getHeader(b'host').split(b':', 1)[1]
            port = port or _port

        # Remove port from address parameter, record if required
        if b':' in address:
            address, _port = address.split(b':', 1)
            port = port or _port

        # Use default port if required
        port = port or b'80'

        if request.path.decode().startswith("/reset"):
            rebind_mappings.clear()
            request.setResponseCode(302)
            request.setHeader("Location", "/")
            request.setHeader("Content-Type", "text/html; charset=UTF-8")
            return "Redirecting...".encode()

        # No rebind tag set, generate one and redirect
        tag = domain.split(".")[0]
        if not tag.startswith("t") or len(tag) != 7:
            rebindtag = "t" + "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(6))
            location = "{}://{}.{}:{}{}".format(scheme, rebindtag, domain, port.decode(), request.uri.decode())

            request.setResponseCode(302)
            request.setHeader("Location", location)
            request.setHeader("Content-Type", "text/html; charset=UTF-8")
            return "Redirecting...".encode()

        html_path = find_file(request.path.decode())
        if html_path is None:
            request.setResponseCode(500)
            return "Bad path: {}".format(request.path.decode()).encode()

        timeout = request.args.get(b'timeout', [b'40'])[0]
        path = request.args.get(b'path', [b'/'])[0]

        # Setup the rebind mapping
        rebindtag = domain.split(".")[0][1:]
        rebind_mappings[rebindtag] = {}
        rebind_mappings[rebindtag]["address"] = address.decode().split(":")[0]
        rebind_mappings[rebindtag]["time"] = time.time() + 2

        html = b''
        if os.path.exists(html_path):
            with open(html_path, "rb") as f:
                html = f.read()
        html = html.replace(b'{rebind_timeout}', timeout)
        html = html.replace(b'{rebind_scheme}', scheme.encode())
        html = html.replace(b'{rebind_address}', address)
        html = html.replace(b'{rebind_port}', port)
        html = html.replace(b'{rebind_path}', path)
        return html


def get_record(lookup_name, lookup_cls, lookup_type):
    rebindtag = lookup_name.decode().split(".rebind.")[0]
    preview = rebindtag[0] == "p"
    rebindtag = rebindtag[1:]

    if rebindtag in rebind_mappings:
        if preview or rebind_mappings[rebindtag]["time"] < time.time():
            return rebind_mappings[rebindtag]["address"]

    return "{{ipv4_address}}"


def get_resource(request):
    return RebindPage()

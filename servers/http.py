import logging
import os
import re
import urllib

from OpenSSL import SSL

from twisted.internet import ssl
from twisted.web import http, server, resource

from jsonroutes import JsonRoutes
from servers.http_resources.simple import SimpleResource
from servers.http_resources.forward import ForwardResource
from utils import apply_middlewares, exec_cached_script

logger = logging.getLogger()


class HTTPJsonResource(resource.Resource):
    """
    HTTP resource which serves response based on a JsonRoutes object
    """

    def __init__(self, domain, *args, **kwargs):
        self.filesroot = os.path.abspath(os.path.join("files"))
        self.routes = JsonRoutes(protocol="http", domain=domain)
        self.middlewares = JsonRoutes(protocol="http_middleware")
        super().__init__(*args, **kwargs)

    def getChild(self, name, request):
        # Rebuild the request parts for route matching
        scheme = "https" if request.isSecure() else "http"
        host = request.getRequestHostname().decode("UTF-8") or "-"
        port = request.getHost().port
        path = request.path.decode("UTF-8")
        args = (request.uri.decode("UTF-8").split("?", 1) + [""])[1]

        request_path = path
        request_parts = [request_path]
        if args:
            request_parts.append(request_path + "?" + args)

        request_parts.append("{}://{}{}{}".format(
            scheme,
            host,
            (":%d" % port) if port != {"http": 80, "https": 443}[scheme] else "",
            request_parts[-1]
        ))

        def _getChild(request):
            headers = {}
            resource_path = request_path

            route_descriptor, route_match = self.routes.get_descriptor(*request_parts)
            if route_descriptor is not None:
                headers = route_descriptor.get("headers", {})

                # Forward case
                if "forward" in route_descriptor:
                    # Recreate the URL
                    if route_descriptor.get("recreate_url", True):
                        fscheme, fnetloc, _, _, _, _ = urllib.parse.urlparse(route_descriptor["forward"])
                        url = urllib.parse.urlunparse((fscheme, fnetloc, request.uri.decode("UTF-8"), "", "", ""))
                    else:
                        url = route_descriptor["forward"]

                    replace = route_descriptor.get("replace", [])
                    return ForwardResource(url, headers=headers, replace=replace)
                # Code case
                elif "code" in route_descriptor:
                    code = route_descriptor.get("code", 200)
                    body = route_descriptor.get("body", "").encode("UTF-8")
                    return SimpleResource(request_path, code, headers=headers, body=body)
                # Path case
                elif "path" in route_descriptor:
                    resource_path = route_descriptor["path"]
                    # Replace regex groups in the route path
                    for i, group in enumerate(re.search(route_descriptor["route"], route_match).groups()):
                        if group is not None:
                            resource_path = resource_path.replace("${}".format(i + 1), group)

                # Security: Ensure the absolute resource_path is within the wwwroot!
                # Prepend the resource_path with the wwwroot and canonicalize
                resource_path = os.path.abspath(os.path.join(self.filesroot, resource_path.lstrip("/")))
                if resource_path.startswith(self.filesroot):
                    if os.path.isfile(resource_path):
                        # Security: Don't show the soruce of python files!
                        if os.path.splitext(resource_path)[1].lower() == ".py":
                            try:
                                res = exec_cached_script(resource_path)
                                return resource.IResource(res["get_resource"](request))
                            except Exception:
                                logger.exception("Unahandled exception in exec'd file '{}'".format(resource_path))
                        else:
                            with open(resource_path, "rb") as f:
                                data = f.read()
                            replace = route_descriptor.get("replace", [])
                            if len(replace):
                                data = data.decode()
                                for replace_descriptor in replace:
                                    replacement = replace_descriptor["replacement"]
                                    replacement = replacement.replace("{hostname}", host)
                                    replacement = replacement.replace("{port}", str(port))
                                    replacement = replacement.replace("{path}", path)
                                    data = re.sub(replace_descriptor["pattern"], replacement, data)
                                data = data.encode()
                            return SimpleResource(request_path, 200, headers=headers, body=data)
                    else:
                        logger.debug("File not found '{}'".format(resource_path))

            # Default handling, 404 here
            return SimpleResource(request_path, 404, body=b'Not Found')

        return apply_middlewares(self.middlewares.get_descriptors(*request_parts), _getChild)(request)


class HTTPSite(server.Site):
    """
    A Site which uses python logging
    """

    def log(self, request):
        host = http._escape(request.getRequestHostname() or "-")
        referrer = http._escape(request.getHeader(b"referer") or "-")
        agent = http._escape(request.getHeader(b"user-agent") or "-")
        line = '"{ip:s}" - {scheme:s}://{host:s}:{port:d} {timestamp:s} "{method:s} {uri:s} {protocol:s}" {code:d} {length:s} "{referrer:s}" "{agent:s}"'
        line = line.format(
            ip=http._escape(request.getClientIP() or "-"),
            scheme="https" if request.isSecure() else "http",
            host=host,
            port=request.getHost().port,
            timestamp=self._logDateTime,
            method=http._escape(request.method),
            uri=http._escape(request.uri),
            protocol=http._escape(request.clientproto),
            code=request.code,
            length=str(request.sentLength) or "-",
            referrer=referrer,
            agent=agent,
        )
        logger.info(line)

        if request.content is not None:
            try:
                request.content.seek(0, 0)
                content = request.content.read()
                if len(content):
                    logger.info("Content: {}".format(content.decode("UTF-8")))
            except:
                pass


class SSLContextFactory(ssl.ContextFactory):
    """
    A TLS context factory which selects a certificate from the files/keys directory
    """

    def __init__(self):
        self.ctx = SSL.Context(SSL.TLSv1_METHOD)
        self.ctx.set_tlsext_servername_callback(self.pick_certificate)
        self.tls_ctx = None
        self.middlewares = JsonRoutes(protocol="ssl_middleware")

        dk_path = os.path.join("files", "keys", "domain.key")
        dc_path = os.path.join("files", "keys", "domain.crt")
        if os.path.exists(dk_path) and os.path.exists(dc_path):
            ctx = SSL.Context(SSL.TLSv1_METHOD)
            ctx.use_privatekey_file(dk_path)
            ctx.use_certificate_file(dc_path)
            ctx.use_certificate_chain_file(dc_path)
            self.tls_ctx = ctx
        else:
            raise Exception("Unable to load TLS certificate information")

    def getContext(self):
        return self.ctx

    def pick_certificate(self, connection):
        def _pick_certificate(connection):
            return self.tls_ctx

        # Apply middlewares
        server_name_indication = (connection.get_servername() or b'').decode("UTF-8")
        ctx = apply_middlewares(self.middlewares.get_descriptors(server_name_indication), _pick_certificate)(connection)
        if ctx is not None:
            connection.set_context(ctx)
        else:
            connection.set_context(self.tls_ctx)

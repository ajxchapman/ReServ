import logging
import os
import re
import urllib

from OpenSSL import SSL

from twisted.internet import ssl
from twisted.web import server, script, resource, static, http_headers

from jsonroutes import JsonRoutes
from servers.http_resources.simple import SimpleResource
from servers.http_resources.forward import ForwardResource

logger = logging.getLogger()

class HTTPJsonResource(resource.Resource):
    """
    HTTP resource which serves response based on a JsonRoutes object
    """

    def __init__(self, *args, **kwargs):
        self.registry = static.Registry()
        self.wwwroot = os.path.abspath(os.path.join("files", "wwwroot"))
        self.routes = JsonRoutes(os.path.join("files", "routes", "http_*.json"), key=lambda x: "default" in x)
        super().__init__(*args, **kwargs)

    def getChild(self, name, request):
        request_path = request.path.decode("UTF-8")
        hostname = request.getRequestHostname().decode("UTF-8")
        client_address = request.getClientIP()

        headers = {}
        resource_path = request_path

        route_descriptor = self.routes.get_descriptor(request_path)
        if route_descriptor is not None:
            logger.info("Matched route {}".format(repr(route_descriptor)))

            headers = route_descriptor.get("headers", {})

            # Forward case
            if "forward" in route_descriptor:
                #Recreate the URL
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
                body = route_descriptor.get("body", "")
                return SimpleResource(request_path, code, headers=headers, body=body)
            # Path case
            elif "path" in route_descriptor:
                resource_path = re.sub(route_descriptor["route"], route_descriptor["path"], request_path)

        # Prepend the resource_path with the wwwroot and canonicalize
        resource_path = os.path.abspath(os.path.join(self.wwwroot, resource_path.lstrip("/")))
        # Security: Ensure the absolute resource_path is within the wwwroot!
        if resource_path.startswith(self.wwwroot):
            if os.path.exists(resource_path):
                # Security: Don't show the soruce of python files!
                if os.path.splitext(resource_path)[1].lower() == ".py":
                    try:
                        return resource.IResource(script.ResourceScript(resource_path, self.registry))
                    except:
                        logger.exception("Unahandled exception in exec'd file '{}'".format(resource_path))
                else:
                    with open(resource_path, "r") as f:
                        data = f.read()
                    return SimpleResource(request_path, 200, headers=headers, body=data)

        # Default handling, 404 here
        return super().getChild(name, request)

class HTTPSite(server.Site):
    """
    A Site which uses python logging
    """

    def log(self, request):
        logger.info(self._logFormatter(self._logDateTime, request))

class SSLContextFactory(ssl.ContextFactory):
    """
    A TLS context factory which selects a certificate from the files/keys directory
    """

    def __init__(self):
        self.ctx = SSL.Context(SSL.TLSv1_METHOD)
        self.ctx.set_tlsext_servername_callback(self.pick_certificate)
        self.tls_ctx = None
        try:
            dk_path = os.path.join("files", "keys", "domain.key")
            dc_path = os.path.join("files", "keys", "domain.crt")
            if os.path.exists(dk_path) and os.path.exists(dc_path):
                ctx = SSL.Context(SSL.TLSv1_METHOD)
                ctx.use_privatekey_file(dk_path)
                ctx.use_certificate_file(dc_path)
                ctx.use_certificate_chain_file(dc_path)
                self.tls_ctx = ctx
        except:
            logger.exception("Unable to load TLS certificate information")

    def getContext(self):
        return self.ctx

    def pick_certificate(self, connection):
        if self.tls_ctx is not None:
            connection.set_context(self.tls_ctx)

import logging
import os
import re
import urllib

from OpenSSL import SSL

from twisted.internet import reactor
from twisted.internet import ssl
from twisted.web import http, server, resource
from twisted.web.wsgi import WSGIResource

from jsonroutes import JsonRoutes
from servers.http_resources.simple import SimpleResource
from servers.http_resources.forward import ForwardResource

import utils

logger = logging.getLogger()


class HTTPJsonResource(resource.Resource):
    """
    HTTP resource which serves response based on a JsonRoutes object
    """

    def __init__(self, *args, **kwargs):
        self.filesroot = os.path.abspath(os.path.join("files"))
        self.routes = utils.get_routes()

        super().__init__(*args, **kwargs)

    def getChild(self, name, request):
        # Rebuild the request parts for route matching
        scheme = "https" if request.isSecure() else "http"
        host = request.getRequestHostname().decode("UTF-8") or "-"
        port = request.getHost().port
        path = request.path.decode("UTF-8")
        args = (request.uri.decode("UTF-8").split("?", 1) + [""])[1]

        # Match on any of scheme://host(:port)/path?args, /path?args, /path in that order
        request_path = path
        request_parts = []
        
        request_parts.append("{scheme}://{host}{port}{path}{args}".format(
            scheme=scheme,
            host=host,
            port=(":%d" % port) if port != {"http": 80, "https": 443}[scheme] else "",
            path=request_path,
            args= "?" + args if args else ""
        ))

        if args:
            request_parts.append(request_path + "?" + args)

        request_parts.append(request_path)

        def _getChild(route_descriptor, route_match, request):
            headers = {}
            resource_path = request_path

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

                # Security: Ensure the absolute resource_path is within the `self.filesroot` directory!
                # Prepend the resource_path with the self.filesroot and canonicalize
                resource_path = os.path.abspath(os.path.join(self.filesroot, resource_path.lstrip("/")))
                if resource_path.startswith(self.filesroot):
                    # If the resource_path does not exist, or is a directory, search for an index.py in each url path directory
                    search_path = ""
                    if not os.path.isfile(resource_path):
                        search_dirs = [""] + resource_path.replace(self.filesroot, "").strip("/").split("/")
                        for search_dir in search_dirs:
                            search_path = os.path.join(search_path, search_dir)
                            if os.path.isfile(os.path.join(self.filesroot, search_path, "index.py")):
                                resource_path = os.path.join(self.filesroot, search_path, "index.py")
                                break

                    # If the resource_path exists and is a file
                    if os.path.isfile(resource_path):
                        # Execute python scripts
                        if os.path.splitext(resource_path)[1].lower() == ".py":
                            # Fixup the request path
                            request.postpath.insert(0, request.prepath.pop(0))
                            
                            try:
                                res = utils.exec_cached_script(resource_path)
                                # If the script exports an `app` variable, load it as a WSGI resource
                                if "app" in res:
                                    return WSGIResource(reactor, reactor.getThreadPool(), res["app"])
                                return resource.IResource(res["get_resource"](request))
                            except:
                                # Catch all exceptions and log them
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
                                    replacement = replacement.replace("{scheme}", scheme)
                                    data = re.sub(replace_descriptor["pattern"], replacement, data)
                                data = data.encode()
                            return SimpleResource(request_path, 200, headers=headers, body=data)

                        logger.debug("File not found '{}'".format(resource_path))

            # Default handling, 404 here
            return SimpleResource(request_path, 404, body=b'Not Found')

        route_descriptor, route_match = self.routes.get_descriptor(*request_parts, rfilter=lambda x: x.get("protocol") == "http")
        middlewares = self.routes.get_descriptors(*request_parts, rfilter=lambda x: x.get("protocol") == "http_middleware")
        return utils.apply_middlewares(middlewares, _getChild)(route_descriptor, route_match, request)

class SSLContextFactory(ssl.ContextFactory):
    """
    A TLS context factory which selects a certificate from the files/keys directory
    """

    def __init__(self, dc_path, dk_path=None):
        self.ctx = SSL.Context(SSL.TLSv1_2_METHOD)
        self.ctx.set_tlsext_servername_callback(self.pick_certificate)
        self.tls_ctx = None
        self.routes = utils.get_routes()

        dk_path = dk_path or dc_path
        if os.path.exists(dk_path) and os.path.exists(dc_path):
            ctx = SSL.Context(SSL.TLSv1_2_METHOD)
            ctx.use_privatekey_file(dk_path)
            ctx.use_certificate_file(dc_path)
            ctx.use_certificate_chain_file(dc_path)
            self.tls_ctx = ctx
        else:
            raise Exception("Unable to load TLS certificate information")

    def getContext(self):
        return self.ctx

    def pick_certificate(self, connection):
        def _pick_certificate(server_name_indication, connection):
            return self.tls_ctx

        # Apply middlewares
        server_name_indication = (connection.get_servername() or b'').decode("UTF-8")
        middlewares = self.routes.get_descriptors(server_name_indication, rfilter=lambda x: x.get("protocol") == "ssl_middleware")
        ctx = utils.apply_middlewares(middlewares, _pick_certificate)(server_name_indication, connection)
        if ctx is not None:
            connection.set_context(ctx)
        else:
            connection.set_context(self.tls_ctx)

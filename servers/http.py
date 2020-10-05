import copy
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

logger = logging.getLogger(__name__)


def _write(request, headers, replacements, data):
    """
    Function to apply headers and replacements to rendering responses.

    This relies on some internal Twisted logic, so *could* break in future.
    """
    if not request.startedWriting:
        for header, value in headers.items():
            header = header.encode("UTF-8")
            value = value.encode("UTF-8")
            # HACK: To get around twisted's bizarre handling of http header cases
            # Whilst according to the RFC headers *SHOULD* be treated as case
            # insensitive, some clients and servers obviously haven't stuck
            # to these rules
            if not header.islower():
                request.responseHeaders._caseMappings[header.lower()] = header
            request.setHeader(header, value)

    # NOTE: This will only work if the pattern attempted to be replaced does not
    # appear on a data boundary
    for r in replacements:
        data = re.sub(r["pattern"], r["replacement"], data)
    request.__class__.write(request, data)

def get_script_response(resource_path, request):
    try:
        res = utils.exec_cached_script(resource_path)
        # If the script exports an `app` variable, load it as a WSGI resource
        if "app" in res:
            return WSGIResource(reactor, reactor.getThreadPool(), res["app"])
        elif "get_resource" in res:
            return resource.IResource(res["get_resource"](request))
        raise Exception("Script does not export `app` variable or `get_resource` function.")
    except:
        # Catch all exceptions and log them
        logger.exception("Unahandled exception in exec'd file '{}'".format(resource_path))
    return SimpleResource(500)

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
            response = SimpleResource(404, body=b'Not Found')

            if route_descriptor is not None:
                response_def = route_descriptor.get("response")
                if response_def is not None:
                    response_type = response_def.get("type", "serve")

                    if response_type == "serve":
                        # Replace regex groups in the route path
                        resource_path = response_def["path"]
                        for i, group in enumerate(re.search(route_descriptor["route"], route_match).groups()):
                            if group is not None:
                                resource_path = resource_path.replace("${}".format(i + 1), group)

                        # Security: Ensure the absolute resource_path is within the `self.filesroot` directory!
                        # Prepend the resource_path with the self.filesroot and canonicalize
                        resource_path = os.path.abspath(os.path.join(self.filesroot, resource_path.lstrip("/")))
                        if resource_path.startswith(self.filesroot):
                            # If the resource_path does not exist, or is a directory, search for an index.py in each url path directory
                            if not os.path.isfile(resource_path):
                                search_path = ""
                                search_dirs = [""] + resource_path.replace(self.filesroot, "").strip("/").split("/")
                                for search_dir in search_dirs:
                                    search_path = os.path.join(search_path, search_dir)
                                    if os.path.isfile(os.path.join(self.filesroot, search_path, "index.py")):
                                        resource_path = os.path.join(self.filesroot, search_path, "index.py")
                                        break
                            
                            if os.path.isfile(resource_path):
                                # Execute python scripts
                                if os.path.splitext(resource_path)[1].lower() == ".py":
                                    # Fixup the request path
                                    request.postpath.insert(0, request.prepath.pop(0))
                                    response = get_script_response(resource_path, request)
                                else:
                                    data = b''
                                    with open(resource_path, "rb") as f:
                                        data = f.read()
                                    response = SimpleResource(200, body=data)

                    elif response_type == "script":
                        # Fixup the request path
                        request.postpath.insert(0, request.prepath.pop(0))

                        # Relocate to `base`
                        if "base" in response_def:
                            base = response_def["base"]
                            request.prepath = base.strip("/").encode().split(b'/')
                            if request_path.startswith(base):
                                request.postpath = request_path.split(base, 1)[1].strip("/").encode().split(b'/')

                        # Apply rewrite
                        if "rewrite" in response_def:
                            match = re.search(response_def["rewrite"], request_path)
                            if match:
                                try:
                                    rewrite = match.group(1)
                                except IndexError:
                                    rewrite = match.group(0)
                                finally:
                                    request.postpath = rewrite.encode().split(b'/')
                        response = get_script_response(response_def["path"], request)
                    elif response_type == "raw":
                        code = response_def.get("code", 200)
                        body = response_def.get("body", "").encode("UTF-8")
                        response = SimpleResource(code, body=body)
                    elif response_type == "forward":
                        url = response_def["destination"]
                        if response_def.get("recreate_url", True):
                            fscheme, fnetloc, _, _, _, _ = urllib.parse.urlparse(url)
                            url = urllib.parse.urlunparse((fscheme, fnetloc, request.uri.decode("UTF-8"), "", "", ""))
                        response = ForwardResource(url, headers=response_def.get("request_headers", {}))
                    
                    
                    headers = response_def.get("headers", {})
                    # Take a copy of the `replace` array as we will modify it afterwards
                    replace = copy.deepcopy(response_def.get("replace", []))
                    if len(headers) or len(replace):
                        if len(replace):
                            # Prepare the replacements
                            for replace_descriptor in replace:
                                replacement = replace_descriptor["replacement"]
                                replacement = replacement.replace("{hostname}", host)
                                replacement = replacement.replace("{port}", str(port))
                                replacement = replacement.replace("{path}", path)
                                replacement = replacement.replace("{scheme}", scheme)
                                replace_descriptor["pattern"] = replace_descriptor["pattern"].encode()
                                replace_descriptor["replacement"] = replacement.encode()
                        
                        # Patch request.write to replace headers after rendering and perform replacements
                        request.write = lambda data: _write(request, headers, replace, data)
            
            return response

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

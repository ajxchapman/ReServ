import copy
import logging
import os
import re
from typing import List, Tuple
from urllib.parse import urlparse, urlunparse

from twisted.internet import reactor
from twisted.web import server, resource
from twisted.web.wsgi import WSGIResource

from jsonroutes import JsonRoutes
from servers.http_resources.simple import SimpleResource
from servers.http_resources.forward import ForwardResource

import utils

logger = logging.getLogger(__name__)

class HTTPException(Exception):
    pass

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
        
        # When performing replacements, the content-length is not currently pre-calculated
        if len(replacements):
            request.responseHeaders.removeHeader("content-length")
            request.setHeader("connection", "close")
            

    # NOTE: This will only work if the pattern attempted to be replaced does not
    # appear on a data boundary
    for r in replacements:
        data = re.sub(r["pattern"].encode(), r["replacement"].encode(), data)
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

    def __init__(self, variables: dict, routes: JsonRoutes, opts: dict, *args, **kwargs):
        self.variables = variables
        self.routes = routes
        self.opts = opts
        self.filesroot = os.path.abspath(opts.files_root)

        super().__init__(*args, **kwargs)

    def getChild(self, request_path, request):
        # Rebuild the request URL for route matching
        request.reconstructed_url = "{scheme}://{host}{port}{path_args}".format(
            scheme="https" if request.isSecure() else "http",
            host=request.getRequestHostname().decode() or "-",
            port=f":{request.getHost().port}" if request.getHost().port != {True: 443, False: 80}[request.isSecure()] else "",
            path_args=request.uri.decode()
        )

        def _getChild(route_descriptor, route_match, request):
            response = SimpleResource(404, content=b'Not Found')

            if route_descriptor is not None:
                action_des = route_descriptor.get("action")
                if action_des is not None:
                    response_handler = action_des.get("handler", "serve")

                    # Process replacements
                    parsed_url = urlparse(request.reconstructed_url)
                    match = re.search(route_descriptor["route"], route_match)
                    replacements = {
                        "url" : request.reconstructed_url,
                        "scheme" : parsed_url.scheme,
                        "hostname" : parsed_url.hostname,
                        "port" : str(parsed_url.port or {"http" : 80, "https" : 443}[parsed_url.scheme]),
                        "path" : parsed_url.path,
                        "query" : parsed_url.query,
                        **{str(k) : v for k, v in enumerate(match.groups(), 1)},
                        **match.groupdict()
                    }
                    action_des = utils.replace_variables(action_des, replacements)

                    if response_handler == "raw":
                        code = action_des.get("code", 200)
                        body = action_des.get("body", "").encode("UTF-8")
                        response = SimpleResource(code, content=body)
                    
                    elif response_handler == "serve":
                        # Security: Ensure the absolute resource_path is within the `self.filesroot` directory!
                        # Prepend the resource_path with the self.filesroot and canonicalize
                        resource_path = os.path.abspath(os.path.join(self.filesroot, action_des["path"].lstrip("/")))
                        if resource_path.startswith(self.filesroot):
                            # If the resource_path does not exist, or is a directory, search for an index.py in each url parent directory
                            if not os.path.isfile(resource_path):
                                search_path = resource_path
                                while search_path.startswith(self.filesroot):
                                    resource_path = os.path.join(search_path, "index.py")
                                    if os.path.isfile(resource_path):
                                        break
                                    search_path = os.path.dirname(search_path)
                                
                            if os.path.isfile(resource_path):
                                # Execute python scripts
                                if os.path.splitext(resource_path)[1].lower() == ".py":
                                    # Fixup the request path
                                    request.postpath.insert(0, request.prepath.pop(0))
                                    response = get_script_response(resource_path, request)
                                else:
                                    code = action_des.get("code", 200)
                                    with open(resource_path, "rb") as f:
                                        data = f.read()
                                    response = SimpleResource(code, content=data)

                    elif response_handler == "script":
                        # Fixup the request path
                        request.postpath.insert(0, request.prepath.pop(0))

                        # Relocate to `base`
                        if "base" in action_des:
                            base = action_des["base"]
                            request.prepath = base.strip("/").encode().split(b'/')
                            if request_path.startswith(base):
                                request.postpath = request_path.split(base, 1)[1].strip("/").encode().split(b'/')

                        # Apply rewrite
                        if "rewrite" in action_des:
                            match = re.search(action_des["rewrite"], request_path)
                            if match:
                                try:
                                    rewrite = match.group(1)
                                except IndexError:
                                    rewrite = match.group(0)
                                finally:
                                    request.postpath = rewrite.encode().split(b'/')
                        response = get_script_response(action_des["path"], request)

                    elif response_handler == "forward":
                        url = action_des["destination"]
                        if action_des.get("recreate_url", True):
                            fscheme, fnetloc, _, _, _, _ = urlparse(url)
                            url = urlunparse((fscheme, fnetloc, request.uri.decode(), "", "", ""))
                        response = ForwardResource(url, headers=action_des.get("request_headers", {}))
                    

                    if action_des.get("headers", {}) or action_des.get("replace", []):
                        # Patch request.write to replace headers after rendering and perform replacements
                        request.write = lambda data: _write(request, action_des.get("headers", {}), action_des.get("replace", []), data)
            
            return response

        route_descriptor, route_match, middlewares = self.filter_routes(request.reconstructed_url, method=request.method.decode())
        return utils.apply_middlewares(self.opts, middlewares, _getChild)(route_descriptor, route_match, request)

    def filter_routes(self, uri: str, method: str="GET") -> Tuple[dict, str, List[dict]]:
        parsed_uri = urlparse(uri)
        if parsed_uri.scheme not in ["http", "https"]:
            raise HTTPException(f"Unrecognised scheme '{parsed_uri.scheme}'")

        # Match on any of scheme://host(:port)/path?args, /path?args, /path in that order
        request_parts = [uri]
        if parsed_uri.query:
            request_parts.append(f"{parsed_uri.path}?{parsed_uri.query}")
        request_parts.append(parsed_uri.path)

        route_descriptor = None
        route_match = None
        for _route_descriptor, _route_match in self.routes.get_descriptors(*request_parts, rfilter=lambda x: x.get("protocol") == "http"):
            _action_des = _route_descriptor.get("action")
            if _action_des is None:
                continue
            
            if _action_des.get("method", method) == method:
                route_descriptor = _route_descriptor
                route_match = _route_match
                break

        middlewares = self.routes.get_descriptors(*request_parts, rfilter=lambda x: x.get("protocol") == "http_middleware")
        return route_descriptor, route_match, middlewares

class HTTPJsonServerFactory(server.Site):
    proto = "HTTP"

    # Proxy filter_routes to the HTTPJsonResource object
    def filter_routes(self, uri: str):
        return self.resource.filter_routes(uri)

    def __init__(self, variables: dict, routes: JsonRoutes, files_root: str, *args, **kwargs):
        super().__init__(HTTPJsonResource(variables, routes, files_root), *args, **kwargs)
import logging

from twisted.web import resource, http_headers

logger = logging.getLogger()

class SimpleResource(resource.Resource):
    isLeaf = True

    def __init__(self, path, code, *args, headers={}, body="", **kwargs):
        self.path = path
        self.code = code
        self.headers = headers
        self.body = body
        super().__init__(*args, **kwargs)

    def render(self, request):
        request.setResponseCode(self.code)
        for header, value in self.headers.items():
            header = header.encode("UTF-8")
            value = value.encode("UTF-8")

            # HACK: To get around twisted's bizarre handling of http header cases
            # Whilst according to the RFC headers *SHOULD* be treated as case
            # insensitive, some clients and servers obviously haven't stuck
            # to these rules
            if not header.islower():
                request.responseHeaders._caseMappings[header.lower()] = header
            request.setHeader(header, value)

        if len(self.body):
            if not "Content-Length" in self.headers:
                request.setHeader("Content-Length".encode("UTF-8"), str(len(self.body)).encode("UTF-8"))
        return self.body

from twisted.web import resource, http_headers

class SimpleResource(resource.Resource):
    isLeaf = True

    def __init__(self, code, *args, body=b'', **kwargs):
        self.code = code
        self.body = body
        super().__init__(*args, **kwargs)

    def render(self, request):
        request.setResponseCode(self.code)
        
        if len(self.body):
            request.setHeader("Content-Length".encode("UTF-8"), str(len(self.body)).encode("UTF-8"))
        return self.body

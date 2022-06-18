import io

from twisted.web import server, resource, http_headers

class SimpleResource(resource.Resource):
    isLeaf = True

    def __init__(self, code, *args, content=b'', **kwargs):
        self.code = code
        self.content = content
        super().__init__(*args, **kwargs)

    def render(self, request):
        request.setResponseCode(self.code)
        
        if isinstance(self.content, io.IOBase):
            length = self.content.seek(0, io.SEEK_END)
            request.setHeader("Content-Length".encode("UTF-8"), str(length).encode("UTF-8"))

            print(length, "streaming")
            self.content.seek(0)
            while True:
                data = self.content.read(4096)
                if len(data) == 0:
                    break
                request.write(data)
            self.content.close()
            request.finish()
            return server.NOT_DONE_YET
        
        length = len(self.content)
        request.setHeader("Content-Length".encode("UTF-8"), str(length).encode("UTF-8"))
        return self.content

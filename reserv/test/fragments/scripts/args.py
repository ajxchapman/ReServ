import json

from twisted.web.resource import Resource

class ArgPage(Resource):
    isLeaf = True
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        super().__init__()

    def render(self, request):
        request.setResponseCode(200)
        request.setHeader("X-Args", json.dumps(self.args))
        request.setHeader("X-KWArgs", json.dumps(self.kwargs))
        return "OK".encode()

def get_resource(request, *args, **kwargs):
    return ArgPage(*args, **kwargs)

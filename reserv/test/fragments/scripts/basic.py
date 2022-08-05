from twisted.web.resource import Resource

class BasicPage(Resource):
    isLeaf = True

    def render(self, request):
        request.setResponseCode(200)
        return "OK".encode()

def get_resource(request):
    return BasicPage()

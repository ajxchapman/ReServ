from twisted.internet import task
from twisted.internet import reactor
from twisted.web import resource
from twisted.web import server


class DelayResource(resource.Resource):
    isLeaf = True

    def __init__(self, resp, duration, *args, body=b'', **kwargs):
        self.resp = resp
        self.duration = duration
        super().__init__(*args, **kwargs)

    def delayed_render(self, request):
        request.write(self.resp.render(request))
        request.finish()

    def render(self, request):
        reactor.callLater(self.duration, self.delayed_render, request)
        return server.NOT_DONE_YET

def http_delay(next, route, route_match, request, duration=1):
    resp = next(route, route_match, request)
    return DelayResource(resp, duration)
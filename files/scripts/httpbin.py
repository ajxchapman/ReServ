import httpbin

from twisted.internet import reactor
from twisted.web.wsgi import WSGIResource


def get_resource(request):
    return WSGIResource(reactor, reactor.getThreadPool(), httpbin.app)

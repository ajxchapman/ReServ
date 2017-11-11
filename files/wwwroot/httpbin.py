import httpbin

from twisted.internet import reactor
from twisted.web.wsgi import WSGIResource

resource = WSGIResource(reactor, reactor.getThreadPool(), httpbin.app)

import logging

from twisted.internet import reactor, defer, protocol
from twisted.internet.ssl import ClientContextFactory
from twisted.web.client import Agent, URI, ResponseDone, PotentialDataLoss, PartialDownloadError
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer
from twisted.web.http_headers import Headers

logger = logging.getLogger()

# String body producer
@implementer(IBodyProducer)
class StringProducer(object):
    """
    Simple string body producer
    """

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

class WebClientContextFactory(ClientContextFactory):
    """
    Permissive client context which will accept any provided TLS certificate.
    """

    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

class CancelableReadBodyProtocol(protocol.Protocol):
    """
    A cancelable protocol which can abort a read based on the amount of data
    read or a timeout.
    """

    def __init__(self, status, message, deferred, data_limit=0, timeout=4.0):
        self.status = status
        self.message = message
        self.deferred = deferred
        self.data_limit = data_limit
        self.timeout = timeout
        self.dataBuffer = []
        self.dataLen = 0
        self.deferred.addTimeout(self.timeout, reactor, onTimeoutCancel=self.handle_timeout)

    def dataReceived(self, data):
        self.dataBuffer.append(data)
        self.dataLen += len(data)

        # Stop consuming data if we have reached the data limit
        if self.data_limit > 0:
            if self.dataLen > self.data_limit:
                # Close the connection
                self.transport.stopProducing()

    def handle_timeout(self, *_):
        self.transport.stopProducing()
        # Raise as we are already in the deferred callback chain here
        raise PartialDownloadError(self.status, self.message, b''.join(self.dataBuffer))

    def connectionLost(self, reason):
        # Only start the callback chain if the deferred has not alreaby been called,
        # e.g. through a timeout
        if not self.deferred.called:
            if reason.check(ResponseDone):
                self.deferred.callback(b''.join(self.dataBuffer))
            else:
                # On an error return a PartialDownload response with whatever data we have already received
                self.deferred.errback(PartialDownloadError(self.status, self.message, b''.join(self.dataBuffer)))

class HTTPJsonClient(Agent):
    """
    A forgiving HTTP client
    """

    def __init__(self, reactor, data_limit=0, timeout=4.0, contextFactory=WebClientContextFactory()):
        self.data_limit = data_limit
        self.timeout = timeout
        super().__init__(reactor, connectTimeout=timeout, contextFactory=contextFactory)

    def read_response(self, response, uri):
        def _read_response_success(body, response):
            response.body = body
            response.partial_download = False
            return response
        def _read_response_failure(failure, response):
            response.body = getattr(failure.value, "response", b'')
            response.partial_download = True
            return response

        # Record the URL of the response
        # If we have a no-standard path, record it encapsulated in square brackets,
        # e.g. http://www.example.com/[http://test.webhooks.pw]
        if not uri.path.startswith(b'/'):
            old_path = uri.path
            uri.path = b'[' + uri.path + b']'
            response.raw_url = uri.toBytes()
            uri.path = old_path
        else:
            response.raw_url = uri.toBytes()

        response.raw_headers = response.headers

        # Decode raw data to usable utf-8 strings
        response.url = response.raw_url.decode("UTF-8")
        response.headers = {k.decode("UTF-8") : [x.decode("UTF-8") for x in v] for k,v in response.raw_headers.getAllRawHeaders()}

        deferred = defer.Deferred()
        protocol = CancelableReadBodyProtocol(response.code, response.phrase, deferred, data_limit=self.data_limit, timeout=self.timeout)
        response.deliverBody(protocol)
        deferred.addCallback(_read_response_success, response)
        deferred.addErrback(_read_response_failure, response)
        return deferred

    def get(self, uri):
        headers = Headers()
        headers.addRawHeader("accept", "*/*")
        return self.request("GET", uri, headers=headers)

    def post(self, uri, data):
        headers = Headers()
        headers.addRawHeader("accept", "*/*")
        return self.request("POST", uri, headers=headers, bodyProducer=StringProducer(data))

    def put(self, uri, data):
        headers = Headers()
        headers.addRawHeader("accept", "*/*")
        return self.request("PUT", uri, headers=headers, bodyProducer=StringProducer(data))

    def request(self, method, uri, headers=None, bodyProducer=None, address=None, path=None):
        """
        Adapted from Agent.request but to allow arbitrary text in the request path, e.g. 'GET http://www.example.com HTTP/1.1'

        Path argument can be used to specifically override the path in the uri for non-conforming paths
        Address argument can be used to override the address the url connection is made to
        """
        method = method.encode("UTF-8")
        parsedURI = URI.fromBytes(uri.encode("UTF-8"))

        try:
            if address is not None:
                modifiedURI = URI.fromBytes(uri.encode("UTF-8"))
                modifiedURI.host = address.encode("UTF-8")
                endpoint = self._getEndpoint(modifiedURI)
            else:
                endpoint = self._getEndpoint(parsedURI)
        except SchemeNotSupported:
            return defer.fail(Failure())

        parsedURI.path = path.encode("UTF-8") if path is not None else parsedURI.path
        key = (parsedURI.scheme, parsedURI.host, parsedURI.port)
        d = self._requestWithEndpoint(key, endpoint, method, parsedURI, headers, bodyProducer, parsedURI.originForm)

        # Add a timeout to the deferred to prevent hangs on requests that connect but don't send any data
        d.addTimeout(self.timeout, reactor)
        d.addCallback(self.read_response, parsedURI)
        return d

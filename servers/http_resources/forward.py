import logging
import re

from twisted.web import server, resource, client, http_headers
from twisted.internet import reactor

import clients.http

logger = logging.getLogger()

class ForwardResource(resource.Resource):
    isLeaf = True

    def __init__(self, uri, *args, headers={}, replace=[], **kwargs):
        self.uri = uri
        self.headers = headers
        self.replace = replace
        self.agent = clients.http.HTTPJsonClient(reactor)
        super().__init__(*args, **kwargs)

    def deliver_deferred_response(self, response, request):
        try:
            request.setResponseCode(response.code, response.phrase)
            for header, values in response.headers.items():
                request.responseHeaders.setRawHeaders(header, values)

            body = response.body
            if len(self.replace):
                body = body.decode("UTF-8")
                for replace_descriptor in self.replace:
                    body = re.sub(replace_descriptor["pattern"], replace_descriptor["replacement"], body)
                body = body.encode("UTF-8")
            request.write(body)
            request.finish()
        except:
            logger.exception("Unhandled exception")

    def deliver_deferred_error(self, err, request):
        request.setResponseCode(500)
        logger.error(str(err))
        logger.info(repr({k.decode("UTF-8") : [v.decode("UTF-8")] for k, v in request.getAllHeaders().items()}))
        request.write(str(err).encode("UTF-8"))
        request.finish()

    def render(self, request):
        #Recreate and fix up the headers
        headers = {k.decode("UTF-8") : [v.decode("UTF-8")] for k, v in request.getAllHeaders().items()}
        #Content-Length is set by the agent, having it set here will cause 2 headers to be sent
        for header in ["content-length", "host", "transfer-encoding", "accept-encoding"]:
            if header in headers:
                del headers[header]
        headers["connection"] = ["close"]


        for header, value in self.headers.items():
            headers[header] = [value]

        deferred = self.agent.request(request.method.decode("UTF-8"), self.uri, http_headers.Headers(headers), client.FileBodyProducer(request.content))
        deferred.addCallback(self.deliver_deferred_response, request)
        deferred.addErrback(self.deliver_deferred_error, request)
        return server.NOT_DONE_YET

from twisted.web.test.requesthelper import DummyRequest

class HttpRequest(DummyRequest):
    def __init__(self, parsed_uri, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.startedWriting = False
        self._serverName = parsed_uri.hostname.encode()
        self.uri = parsed_uri.path
        if len(parsed_uri.query):
            self.uri += "?" + parsed_uri.query
        self.uri = self.uri.encode()
        print('URI', self.uri, parsed_uri.scheme)
        self.secure = parsed_uri.scheme == 'https'
        
        # Fake pre and post path
        self.postpath = parsed_uri.path[1:].split("/")
        self.prepath = [self.postpath.pop(0)]

    def isSecure(self):
        return self.secure

    def write(self, data):
        super().write(data)
        self.startedWriting = True

    def getResponseHeader(self, name):
        return self.responseHeaders.getRawHeaders(name.lower(), [None])[0]
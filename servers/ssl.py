import os

from OpenSSL import SSL
from twisted.internet import ssl

import utils

class SSLContextFactory(ssl.ContextFactory):
    """
    A TLS context factory which selects a certificate from the files/keys directory
    """

    def __init__(self, dc_path, dk_path=None):
        self.ctx = SSL.Context(SSL.TLSv1_2_METHOD)
        self.ctx.set_tlsext_servername_callback(self.pick_certificate)
        self.tls_ctx = None
        self.routes = utils.get_routes()

        dk_path = dk_path or dc_path
        if os.path.exists(dk_path) and os.path.exists(dc_path):
            ctx = SSL.Context(SSL.TLSv1_2_METHOD)
            ctx.use_privatekey_file(dk_path)
            ctx.use_certificate_file(dc_path)
            ctx.use_certificate_chain_file(dc_path)
            self.tls_ctx = ctx
        else:
            raise Exception("Unable to load TLS certificate information")

    def getContext(self):
        return self.ctx

    def pick_certificate(self, connection):
        def _pick_certificate(server_name_indication, connection):
            return self.tls_ctx

        # Apply middlewares
        server_name_indication = (connection.get_servername() or b'').decode("UTF-8")
        middlewares = self.routes.get_descriptors(server_name_indication, rfilter=lambda x: x.get("protocol") == "ssl_middleware")
        ctx = utils.apply_middlewares(middlewares, _pick_certificate)(server_name_indication, connection)
        if ctx is not None:
            connection.set_context(ctx)
        else:
            connection.set_context(self.tls_ctx)
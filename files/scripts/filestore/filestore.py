import logging
import os
import uuid

from twisted.web.resource import Resource

# TODO: Max file size
# TODO: Max number of files

logger = logging.getLogger("server_log")

class StorePage(Resource):
    isLeaf = True

    def render(self, request):
        if not os.path.isdir("/tmp/filestore"):
            os.makedirs("/tmp/filestore")
        
        file_id = str(uuid.uuid4())
        logger.info(f"Storing {request.uri.decode()} as {file_id}")
        with open(f"/tmp/filestore/{file_id}", "wb") as f:
            request.content.seek(0, 0)
            while True:
                data = request.content.read()
                if len(data):
                    f.write(data)
                else:
                    break
        request.setResponseCode(202)
        return "OK".encode()


def get_resource(request):
    return StorePage()

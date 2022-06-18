import os.path
import subprocess
import json

from twisted.web.resource import Resource

repo_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "repo")
class GitWebPage(Resource):
    isLeaf = True

    def render_POST(self, request):
        path = request.path.decode()
        print(path)
        if path.endswith("/git-upload-pack"):
            cmd = ["git", "upload-pack", "--stateless-rpc", repo_directory]
            result = subprocess.run(cmd, input=request.content.read(), stdout=subprocess.PIPE)
            request.setHeader("Content-Type", "application/x-git-upload-pack-result")
            return result.stdout

        elif path.endswith("/info/lfs/objects/batch"):
            lfs_req = json.loads(request.content.read().decode())
            if lfs_req["operation"] == "download":
                lfs_resp = {"objects" : []}
                for obj in lfs_req["objects"]:
                    lfs_resp["objects"].extend([{
                        "oid" : obj["oid"],
                        "size" : obj["size"],
                        "actions" : {
                            "download": {
                                "href" : "http://git.webhooks.pw/httpbin/redirect-to?url=http://gitfiles.webhooks.pw/metadata/v1/",
                                "header" : {"Test" : "Value"}
                            }
                        }
                    }] * 20)
                request.setHeader("Content-Type", "application/json; charset=utf-8")
                return json.dumps(lfs_resp).encode()
        return b''

    def render_GET(self, request):
        path = request.path.decode()
        print(path)
        if path.endswith("/info/refs"):
            service = request.args.get(b'service')[0].decode()
            if service == "git-upload-pack":
                cmd = ["git", "upload-pack", "--stateless-rpc", "--advertise-refs", repo_directory]
                result = subprocess.run(cmd, stdout=subprocess.PIPE)
                request.setHeader("Content-Type", "application/x-git-upload-pack-advertisement")
                return b'001e# service=git-upload-pack\n0000' + result.stdout # No idea what this is
        elif path.endswith("/HEAD"):
            with open(os.path.join(repo_directory, "HEAD"), "rb") as f:
                return f.read()
        return b''

def get_resource(request):
    return GitWebPage()


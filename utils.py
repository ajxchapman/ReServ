import logging
import socket
import os


logger = logging.getLogger()


def get_ipv4_address(dest="8.8.8.8"):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((dest, 80))
    return s.getsockname()[0]


def get_ipv6_address(dest="::1"):
    # TODO
    return "::1"


def apply_middlewares(routes, next_function):
    # Apply middlewares
    _func = next_function
    for middleware, _ in routes[::-1]:
        _middleware_module_name = middleware.get("module", None)
        if _middleware_module_name is None:
            logger.error("No module name specified for middleware")
            continue

        _middleware_function_name = middleware.get("function", None)
        if _middleware_function_name is None:
            logger.error("No function name specified for middleware")
            continue

        try:
            _middleware_module = exec_cached_script(_middleware_module_name)
        except Exception:
            logger.exception("Unable to import middleware '{}'".format(_middleware_module_name))
            continue

        _middleware_func = _middleware_module.get(_middleware_function_name, None)
        if _middleware_func is None:
            logger.error("Middleware funcion '{}' does not exist in '{}'".format(_middleware_function_name, _middleware_module_name))
            continue

        _args = middleware.get("args", [])
        _kwargs = middleware.get("kwargs", {})

        _func = (lambda m, f, a, k: lambda r: m(r, f, *a, **k))(_middleware_func, _func, _args, _kwargs)
    return _func

script_cache = {}
def exec_cached_script(path):
    path = os.path.abspath(os.path.join(os.path.split(__file__)[0], "files", path))
    cache = script_cache.setdefault(path, {"mtime": 0, "vars": {}})
    if cache["mtime"] < os.path.getmtime(path):
        with open(path) as f:
            code = compile(f.read(), path, "exec")
            _vars = {}
            exec(code, _vars, _vars)
            cache["vars"] = _vars
            cache["mtime"] = os.path.getmtime(path)
    return cache["vars"]

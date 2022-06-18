import json
import logging
import os
import random
import re
import socket

logger = logging.getLogger()


_variables = None
def get_variables(config):
    global _variables
    if _variables is not None:
        return _variables

    # Set some default variables, these will be overwritten if they appear in the config
    _variables = {
        "ipv4_address" : get_ipv4_address(),
        "ipv6_address" : get_ipv6_address()
    }
    _variables = {**_variables, **config.get("variables", {})}
    return _variables

def replace_variables(obj, replacements):
    if isinstance(obj, str):
        for variable in re.findall("((?:\{\{)[A-Za-z0-9_-]+(?:\}\})|\$[0-9]+)", obj):
            obj = obj.replace(variable, str(replacements.get(variable.strip("${}"), "")))
    elif isinstance(obj, list):
        obj = [replace_variables(value, replacements) for value in obj]
    elif isinstance(obj, dict):
        obj = {key: replace_variables(value, replacements) for key, value in obj.items()}
    return obj

def get_config(path):
    if not os.path.isfile(path):
        raise Exception(f"Config file '{path}' does not exist")
    
    # Set default values
    _config = {
        "variables": {
            "secret_key" : "".join(chr(random.randint(0, 128)) for x in range(32)),
            "credentials" : [
                {
                    "user" : "admin",
                    "password" : "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") for x in range(16))
                }
            ]
        }
    }

    with open(path) as f:
        _config = {**_config, **json.load(f)}
    with open(path, "w") as f:
            json.dump(_config, f, indent=4)
    return _config

def get_ipv4_address(dest="8.8.8.8", port=80):
    """
    Get ipv4 address for a given destination. By default use Google's ipv4 DNS
    assress.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((dest, port))
        return s.getsockname()[0]
    except OSError:
        pass
    return "127.0.0.1"


def get_ipv6_address(dest="2001:4860:4860::8888", port=80):
    """
    Get ipv6 address for a given destination. By default use Google's ipv6 DNS
    assress.
    """
    s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    try:
        s.connect((dest, port))
        return s.getsockname()[0]
    except OSError:
        pass
    return "::1"


def apply_middlewares(routes, next_function):
    # Apply middlewares
    _func = next_function
    for middleware, _ in routes[::-1]:
        middleware_des = middleware.get("action")
        _middleware_module_name = middleware_des.get("module")
        if _middleware_module_name is None:
            logger.error("No module name specified for middleware")
            continue

        _middleware_function_name = middleware_des.get("function")
        if _middleware_function_name is None:
            logger.error("No function name specified for middleware")
            continue

        try:
            _middleware_module = exec_cached_script(_middleware_module_name)
        except Exception:
            logger.exception("Unable to import middleware '{}'".format(_middleware_module_name))
            continue

        _middleware_func = _middleware_module.get(_middleware_function_name)
        if _middleware_func is None:
            logger.error("Middleware funcion '{}' does not exist in '{}'".format(_middleware_function_name, _middleware_module_name))
            continue

        _args = middleware_des.get("args", [])
        _kwargs = middleware_des.get("kwargs", {})

        _func = (lambda m, f, a, k: lambda *args, **kwargs: m(f, *[*args, *a], **{**kwargs, **k}))(_middleware_func, _func, _args, _kwargs)
    return _func

script_cache = {}
def exec_cached_script(path):
    path = os.path.abspath(os.path.join(os.path.split(__file__)[0], "files", path))
    if not path.startswith(os.path.abspath(os.path.join(os.path.split(__file__)[0], "files"))):
        raise Exception("Attempted to load script '{}' from outside the `files` directory.".format(path))
    cache = script_cache.setdefault(path, {"mtime": 0, "vars": {}})
    if cache["mtime"] < os.path.getmtime(path):
        with open(path) as f:
            code = compile(f.read(), path, "exec")
            _vars = {"__file__": path, "__name__": os.path.splitext(os.path.basename(path))[0]}
            exec(code, _vars, _vars)
            cache["vars"] = _vars
            cache["mtime"] = os.path.getmtime(path)
    return cache["vars"]

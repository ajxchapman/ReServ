import logging
import importlib


logger = logging.getLogger()


def apply_middlewares(routes, match, next_function):
    # Apply middlewares
    _func = next_function
    for middleware in routes.get_descriptors(match)[::-1]:
        _middleware_module_name = middleware.get("module", None)
        if _middleware_module_name is None:
            logger.error("No module name specified for middleware")
            continue

        _middleware_function_name = middleware.get("function", None)
        if _middleware_function_name is None:
            logger.error("No function name specified for middleware")
            continue

        try:
            _middleware_module = importlib.import_module(_middleware_module_name)
        except Exception:
            logger.exception("Unable to import middleware '{s}'", _middleware_module_name)
            continue

        _middleware_func = getattr(_middleware_module, _middleware_function_name, None)
        if _middleware_func is None:
            logger.error("Middleware funcion '{s}' does not exist in '{s}'", _middleware_function_name, _middleware_module_name)
            continue

        _args = middleware.get("args", [])
        _kwargs = middleware.get("kwargs", {})

        _func = (lambda m, f, a, k: lambda r: m(r, f, *a, **k))(_middleware_func, _func, _args, _kwargs)
    return _func

import glob
import json
import logging
import os
import re
import time

logger = logging.getLogger()

class JsonRoutes(object):
    """
    Helper class to watch a set of JSON files and reload any that have changed.
    """
    DEFAULT_SORT_KEY=lambda x: 100 if os.path.basename(x).startswith("default") else int((re.findall("^[0-9]+", os.path.basename(x)) + ["99"])[0])

    def __init__(self, *args, key_func=None, cache_invalidate_time=60, variables={}, **kwargs):
        self.path_globs = list(args)
        self.key_func = key_func or JsonRoutes.DEFAULT_SORT_KEY
        self.cache_invalidate_time = cache_invalidate_time
        self.format_args = {**{str(k).upper() : v for k, v in variables.items()}, **{str(k).upper() : v for k, v in kwargs.items()}}

        self._cache = {}
        self._cache_update = 0
        self.json_routes = {}
        self._route_descriptors = []
        self._update_route_descriptors()

    def replace_variables(self, repl, regex=False):
        if isinstance(repl, str):
            for variable in re.findall("\{\{([A-Za-z0-9_-]+)\}\}", repl):
                # Don't use string format to avoid key errors with regex syntax, e.g. '[0-2]{1, 3}'
                # HACK to allow non-regex string replacements in regex "route" variables
                if regex:
                    repl = repl.replace("{{" + variable + "}}", re.escape(str(self.format_args.get(variable.upper(), ""))))
                else:
                    repl = repl.replace("{{" + variable + "}}", str(self.format_args.get(variable.upper(), "")))
        elif isinstance(repl, list):
            repl = [self.replace_variables(value) for value in repl]
        elif isinstance(repl, dict):
            repl = {key: self.replace_variables(value, regex=key in ["route"]) for key, value in repl.items()}
        return repl

    @property
    def route_descriptors(self):
        self._update_route_descriptors()
        return self._route_descriptors

    def get_descriptor(self, *routes, rfilter=lambda x: True):
        return (self.get_descriptors(*routes, rfilter=rfilter, first=True) or [({}, "")])[0]

    def get_descriptors(self, *routes, rfilter=lambda x: True, first=False):
        self._update_route_descriptors()
        descriptors = []
        for route_descriptor in self._route_descriptors:
            for route in routes:
                # A route_descriptor without a route will match all routes
                if ("route" not in route_descriptor or re.search(route_descriptor["route"], route)) and rfilter(route_descriptor):
                    logger.debug("[!] Matched route {}: {}".format(route, repr(route_descriptor)))
                    descriptors.append((route_descriptor, route))
                    if first:
                        return descriptors

                    # Only record the first matching route_descriptor for a set of routes
                    break
                else:
                    logger.debug("[-] Checked route {}: {}".format(route, repr(route_descriptor)))
        return descriptors

    def _update_route_descriptors(self):
        # Only update the cache if self.cache_invalidate_time seconds have passed
        if time.time() > self._cache_update + self.cache_invalidate_time:
            updated = False
            for path_glob in self.path_globs:
                for rd_path in glob.glob(path_glob, recursive=True):
                    if os.path.isfile(rd_path):
                        mtime = os.path.getmtime(rd_path)
                        if mtime > self._cache.get(rd_path, 0):
                            try:
                                with open(rd_path, "r") as f:
                                    default_sort_index = self.key_func(rd_path)
                                    
                                    # Expand variables
                                    route_descriptors = self.replace_variables(json.load(f))
                                    for route_descriptor in route_descriptors:
                                        # Apply default keys
                                        if not "sort_index" in route_descriptor:
                                            route_descriptor["sort_index"] = default_sort_index
                                        # Compile regular expressions
                                        if "route" in route_descriptor:
                                            route_descriptor["route"] = re.compile(route_descriptor["route"])
                                        route_descriptor["_route_file"] = rd_path
                            except:
                                logger.exception("Unable to parse json rule file '{}'".format(rd_path))
                            else:
                                self._cache[rd_path] = mtime
                                self.json_routes[rd_path] = route_descriptors
                                updated = True

            # If we updated any route descriptors re-sort the internal list
            if updated:
                self._route_descriptors = []
                for route_descriptors in self.json_routes.values():
                    for route_descriptor in route_descriptors:
                        self._route_descriptors.append(route_descriptor)
                self._route_descriptors = sorted(self._route_descriptors, key=lambda x: x["sort_index"])
            
            self._cache_update = time.time()
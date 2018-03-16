import glob
import json
import logging
import os
import re

logger = logging.getLogger()

class JsonRoutes(object):
    """
    Helper class to watch a set of JSON files and reload any that have changed.
    """
    DEFAULT_SORT_KEY=lambda x: 100 if "default" in x else int(''.join(y for y in x if y.isdigit()) or 99)

    def __init__(self, *args, protocol=None, key=None, **kwargs):
        self.path_globs = list(args) or [os.path.join("files", "routes", "*.json")]
        self.protocol = protocol
        self.key = key or JsonRoutes.DEFAULT_SORT_KEY
        self.format_args = {k : re.escape(v) for k, v in kwargs.items()}

        self._cache = {}
        self.json_routes = {}
        self._route_descriptors = []

    @property
    def route_descriptors(self):
        self._update_route_descriptors()
        return self._route_descriptors

    def get_descriptor(self, *routes):
        return (self.get_descriptors(*routes, first=True) or [(None, None)])[0]

    def get_descriptors(self, *routes, first=False):
        self._update_route_descriptors()
        descriptors = []
        for route_descriptor in self._route_descriptors:
            for route in routes:
                if re.search(route_descriptor["route"], route):
                    logger.debug("Matched route {}: {}".format(route, repr(route_descriptor)))
                    descriptors.append((route_descriptor, route))
                    if first:
                        return descriptors

                    # Only record the first matching route_descriptor for a set of routes
                    break
        return descriptors

    def _update_route_descriptors(self):
        updated = False
        for path_glob in self.path_globs:
            for rd_path in glob.glob(path_glob):
                if os.path.isfile(rd_path):
                    mtime = os.path.getmtime(rd_path)
                    if mtime > self._cache.get(rd_path, 0):
                        try:
                            with open(rd_path, "r") as f:
                                route_descriptors = [x for x in json.load(f) if x.get("protocol", None) == self.protocol]
                                for route_descriptor in route_descriptors:
                                    # Cheating string format to avoid key errors with regex syntax, e.g. '[0-2]{1, 3}'
                                    for key, value in self.format_args.items():
                                        route_descriptor["route"] = route_descriptor["route"].replace("{" + key + "}", value)
                                    route_descriptor["route"] = re.compile(route_descriptor["route"])
                        except:
                            logger.exception("Unable to parse json rule file '{}'".format(rd_path))
                        else:
                            self._cache[rd_path] = mtime
                            self.json_routes[rd_path] = route_descriptors
                            updated = True

        # If we updated any route descriptors re-sort the internal list
        if updated:
            self._route_descriptors = []
            for json_route in sorted(self.json_routes.keys(), key=self.key):
                self._route_descriptors.extend(self.json_routes[json_route])

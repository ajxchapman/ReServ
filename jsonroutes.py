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

    def __init__(self, *args, key=None, **kwargs):
        self.path_globs = list(args)
        self._cache = {}
        self.json_routes = {}
        self._route_descriptors = []
        self.format_args = {k : re.escape(v) for k, v in kwargs.items()}
        self.key = key

    @property
    def route_descriptors(self):
        self._update_route_descriptors()
        return self._route_descriptors

    def get_descriptor(self, route):
        self._update_route_descriptors()
        for route_descriptor in self._route_descriptors:
            if re.fullmatch(route_descriptor["route"], route):
                return route_descriptor
        return None

    def get_descriptors(self, route):
        self._update_route_descriptors()
        descriptors = []
        for route_descriptor in self._route_descriptors:
            if re.fullmatch(route_descriptor["route"], route):
                descriptors.append(route_descriptor)
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
                                route_descriptors = json.load(f)
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

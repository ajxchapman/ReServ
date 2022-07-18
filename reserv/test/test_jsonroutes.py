import os
import unittest

from jsonroutes import JsonRoutes

class TestJsonRoutes(unittest.TestCase):
    def test_init(self):
        j = JsonRoutes(os.path.join(os.path.dirname(__file__), "fragments", "jsonroutes", "route1.json"))
        
        self.assertEqual(len(j.route_descriptors), 1)

    def test_replace_route(self):
        j = JsonRoutes(os.path.join(os.path.dirname(__file__), "fragments", "jsonroutes", "route1.json"), variables={"REPLACE" : "XXX"})
        
        self.assertEqual(j.route_descriptors[0]["route"].pattern, "XXX")
    
    def test_replace_var(self):
        j = JsonRoutes(os.path.join(os.path.dirname(__file__), "fragments", "jsonroutes", "route1.json"), variables={"REPLACE" : "XXX"})

        self.assertEqual(j.replace_variables("{{REPLACE}}"), "XXX")
        self.assertEqual(j.replace_variables(["{{REPLACE}}"]), ["XXX"])
        self.assertEqual(j.replace_variables({"key" : "{{REPLACE}}"}), {"key" : "XXX"})
        self.assertEqual(j.replace_variables({"key" : ["{{REPLACE}}"]}), {"key" : ["XXX"]})

        # Should just return non-matching values, or none replaceable values
        self.assertEqual(j.replace_variables("test"), "test")
        self.assertEqual(j.replace_variables(123), 123)
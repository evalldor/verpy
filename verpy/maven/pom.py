import typing
import re
from pyparsing import makeXMLTags, SkipTo, Word, alphanums, Group, Empty, ZeroOrMore, htmlComment

import bs4
import xmltodict

from pprint import pformat


class EffectivePom:
    """To determine the depenencies of an artifact, an 'Effective POM' has to 
    be built."""
    def __init__(self):
        self._pom_stack = []

    def push(self, properties, dependencies, dependency_management):
        self._pom_stack.append({
            "properties": properties,
            "dependencies": dependencies,
            "dependency_management": dependency_management
        })


class Pom:

    def __init__(self, xml_string):
        self._pom = xmltodict.parse(xml_string)

    @property
    def parent(self):
        try:
            return self._pom["project"]["parent"]
        except KeyError:
            return None

    @property
    def profiles(self):
        try:
            return self._pom["project"]["profiles"]["profile"]
        except KeyError:
            return []

    @property
    def properties(self):
        try:
            return self._pom["project"]["properties"]
        except KeyError:
            return {}

    @property
    def dependency_management(self):
        try:
            return self._pom["project"]["dependencyManagement"]["dependencies"]["dependency"]
        except KeyError:
            return []

    @property
    def dependencies(self):
        try:
            return self._pom["project"]["dependencies"]["dependency"]
        except KeyError:
            return []


def interpolate(string, properties):

    PROPERY_PATTERN = r"(?P<pattern>\$\{(?P<name>.*?)\})"

    interpolated = string

    match = re.search(PROPERY_PATTERN, interpolated)

    while match is not None:
        pattern = match.group("pattern")
        name = match.group("name")
        
        if name not in properties:
            raise Exception(f"Property {name} does not exist.")

        interpolated = interpolated.replace(pattern, properties[name])

        match = re.search(PROPERY_PATTERN, interpolated)

    return interpolated

import dataclasses
import typing
import re
import itertools

from pyparsing import (
    Literal,
    CaselessLiteral,
    Word, 
    Empty, 
    alphanums, 
    delimitedList, 
    Group, 
    nums, 
    alphas, 
    ZeroOrMore, 
    nestedExpr, 
    Forward, 
    OneOrMore, 
    Optional, 
    infixNotation, 
    opAssoc, 
    ungroup
)


def as_version(version):
    """Takes a string and parses it into a :class:`Version` instance. The input
    is also allowed to be an instance of :class:`Version`, in which case it is
    returned unmodified.

    Args: version (str): The string to parse

    Raises: ValueError: If the input is not a string

    Returns: :class:`Version`: The parsed version
    """

    if isinstance(version, Version):
        return version

    if isinstance(version, str):
        return Version(version)

    raise ValueError(f"Invalid version type '{type(version)}'.")


def as_set(specifier):
    """Parses the provided string into a :class:`VersionSet` instance. If the is
    already an instance of :class:`VersionSet` it is returned unmodified. If it
    is an instance of :class:`Version` a set containing the single version is
    returned.

    Args:
        specifier (str): The version set string to parse

    Raises:
        ValueError: If the input is not an instance of str, :class:`Version` or 
        :class:`VersionSet`.

    Returns:
        :class:`VersionSet`: A set of versions.
    """
    if isinstance(specifier, VersionSet):
        return specifier

    if isinstance(specifier, str):
        return parse_version_set(specifier)

    if isinstance(specifier, Version):
        return EqSpecifier(as_version(specifier))
    
    raise ValueError(f"Invalid set type '{type(specifier)}'.")


def as_requirement(requirement):
    """Parses the given string into a :class:`Requirement` instance. A
    requirement consists of a package name and an allowed version set. E.g.
    ``verpy >=1.5.0``

    Args:
        requirement (str): The string to parse

    Raises:
        ValueError: If the input is of an unknown type.

    Returns:
        :class:`Requirement`: 
    """
    if isinstance(requirement, Requirement):
        return requirement
    
    if isinstance(requirement, str):
        return Requirement.from_string(requirement)

    raise ValueError(f"Invalid requirement type '{type(requirement)}'.")


def as_python_requirement(requirement):
    pass


def as_maven_set(specifier):
    if isinstance(specifier, VersionSet):
        return specifier

    if isinstance(specifier, str):
        return parse_maven_version_set(specifier)

    if isinstance(specifier, Version):
        return EqSpecifier(as_version(specifier))
    
    raise ValueError(f"Invalid set type '{type(specifier)}'.")


def intersection_of(*sets):
    return VersionSet.all(*[as_set(s) for s in sets])


def union_of(*sets):
    return VersionSet.any(*[as_set(s) for s in sets])


#
# Version parsing
#
"""
'-' and transition between digits and character constitues a component boundary. 
'.' separates items within a component
"""
NUMERIC_PART = Word(nums+".").setParseAction(lambda x: NumericComponent(x[0]))
STRING_PART = Word(alphas+".").setParseAction(lambda x: StringComponent(x[0]))
COMPONENT = NUMERIC_PART ^ STRING_PART
SEPARATOR = Literal("-").suppress()
SECTION = COMPONENT ^ SEPARATOR
PREFIX = Optional(CaselessLiteral("v") ^ CaselessLiteral("ver") ^ CaselessLiteral("version")).suppress()

VERSION_PATTERN = PREFIX + OneOrMore(SECTION)

string_version_orderings = {
    "alpha": 0,
    "a": 0,
    "beta": 1,
    "b": 1,
    "milestone": 2,
    "m": 2,
    "rc": 3,
    "cr": 3,
    "c": 3,
    "": 4,
    "snapshot": 5,
    "dev": 5,
    "final": 6,
    "ga": 6,
    "post": 7,
    "sp": 7
}


class Version:

    def __init__(self, version_string):
        self._string_representation = version_string # This is saved because often one wants to preserve the original formatting
        self._parsed_representation = None

    def _str_repr(self):
        return self._string_representation

    def _formatstr_repr(self):
        return "-".join([str(c) for c in self._parsed_repr()])

    def _parsed_repr(self):
        if self._parsed_representation is None:
            components = VERSION_PATTERN.parseString(self._str_repr(), parseAll=True)

            self._parsed_representation = components

        return self._parsed_representation 
    
    def _norm_repr(self):
        return tuple(itertools.chain([c.normalized_representation() for c in self._parsed_repr()]))

    def __gt__(self, other):
        return compare_versions(self._parsed_repr(), other._parsed_repr()) > 0

    def __lt__(self, other):
        return compare_versions(self._parsed_repr(), other._parsed_repr()) < 0

    def __ge__(self, other):
        return compare_versions(self._parsed_repr(), other._parsed_repr()) >= 0

    def __le__(self, other):
        return compare_versions(self._parsed_repr(), other._parsed_repr()) <= 0

    def __eq__(self, other):
        return compare_versions(self._parsed_repr(), other._parsed_repr()) == 0

    def __ne__(self, other):
        return compare_versions(self._parsed_repr(), other._parsed_repr()) != 0

    def __str__(self):
        return f"{self._str_repr()}"

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash(self._norm_repr())


class NumericComponent:
    def __init__(self, num_string):
        self._items = [int(i) for i in num_string.split(".") if i is not None and len(i) > 0]

    def __str__(self):
        return ".".join([str(i) for i in self._items])
    
    def __repr__(self):
        return str(self)

    def normalized_representation(self):
        """Used when hashing"""
        leading_non_zero_items = []

        for i in self._items:
            if i == 0:
                break
            leading_non_zero_items.append(i)

        return tuple(leading_non_zero_items)

    def __hash__(self):
        return hash(self.normalized_representation())


class StringComponent:
    def __init__(self, string):
        self._item = str(string).strip(".")

    def normalized_representation(self):
        """Used when hashing"""
        return tuple([str(self).lower()])

    def __str__(self):
        return self._item
    
    def __repr__(self):
        return str(self)


class NullComponent:
    pass


GREATER = 1
LESSER = -1
EQUAL = 0


def compare_versions(a_components, b_components):

    l = max(len(a_components), len(b_components))
        
    while len(a_components) < l:
        a_components.append(NullComponent())

    while len(b_components) < l:
        b_components.append(NullComponent())

    for i in range(l):
        c = compare_version_components(a_components[i], b_components[i])
        if c != 0:
            return c

    return EQUAL


def compare_version_components(a, b):

    if isinstance(a, NullComponent):
        return -1*compare_component_with_null(b)

    if isinstance(b, NullComponent):
        return compare_component_with_null(a)

    #Numberic components > string components always
    if isinstance(a, NumericComponent) and isinstance(b, StringComponent):
        return GREATER

    elif isinstance(a, StringComponent) and isinstance(b, NumericComponent):
        return LESSER

    elif isinstance(a, NumericComponent) and isinstance(b, NumericComponent):
        l = max(len(a._items), len(b._items))
        
        a_items = [*a._items]
        while len(a_items) < l:
            a_items.append(0)

        b_items = [*b._items]
        while len(b_items) < l:
            b_items.append(0)
        
        for a_item, b_item in zip(a_items, b_items):
            if a_item > b_item:
                return GREATER
            if a_item < b_item:
                return LESSER

        return EQUAL

    elif isinstance(a, StringComponent) and isinstance(b, StringComponent):

        a_item = a._item.lower()
        b_item = b._item.lower()
    
        if a_item in string_version_orderings and b_item in string_version_orderings:
            if string_version_orderings[a_item] > string_version_orderings[b_item]:
                return GREATER
                
            if string_version_orderings[a_item] < string_version_orderings[b_item]:
                return LESSER

        elif a_item in string_version_orderings and b_item not in string_version_orderings:
            return GREATER
        
        elif a_item not in string_version_orderings and b_item in string_version_orderings:
            return LESSER

        elif a_item > b_item:
            return GREATER

        elif a_item < b_item:
            return LESSER

        return EQUAL

    raise Exception("Unknown components types")


def compare_component_with_null(a):

    if isinstance(a, NumericComponent):
        return GREATER
    
    if isinstance(a, StringComponent):
        a_item = a._item.lower()
        if a_item in string_version_orderings:
            if string_version_orderings[a_item] > string_version_orderings[""]:
                return GREATER

            if string_version_orderings[a_item] < string_version_orderings[""]:
                return LESSER

            return EQUAL #Should never happend, but just to be safe..
        
        return LESSER
    
    raise Exception("Internal Error.")


class VersionSet:
    
    def __or__(self, other):
        return OrOperator(self, as_set(other))

    def __and__(self, other):
        return AndOperator(self, as_set(other))

    def __invert__(self):
        return NotOperator(self)

    def __contains__(self, version):
        return self.contains(as_version(version))

    def union(self, specifier):
        return self | as_set(specifier)

    def intersection(self, specifier):
        return self & as_set(specifier)
    
    def complement(self):
        return ~self

    def difference(self, specifier):
        return self.intersection(~as_set(specifier))

    def contains(self, version):
        return self.allows_version(as_version(version))

    def allows_version(self, version):
        #This method is implemented in the subclasses.
        raise NotImplementedError()

    def filter_allowed(self, versions):
        return list(filter(self.allows_version, [as_version(v) for v in versions]))

    @staticmethod
    def from_string(string):
        return parse_version_set(string)

    @staticmethod
    def eq(version):
        return EqSpecifier(as_version(version))

    @staticmethod
    def neq(version):
        return NotEqSpecifier(as_version(version))

    @staticmethod
    def gteq(version):
        return GtEqSpecifier(as_version(version))

    @staticmethod
    def lteq(version):
        return LtEqSpecifier(as_version(version))

    @staticmethod
    def gt(version):
        return GtSpecifier(as_version(version))

    @staticmethod
    def lt(version):
        return LtSpecifier(as_version(version))
    
    @staticmethod
    def none():
        return NoneSpecifier()

    @staticmethod
    def all(*specifiers):
        if len(specifiers) == 1:
            return as_set(specifiers[0])

        return AndOperator(*[as_set(spec) for spec in specifiers])
    
    @staticmethod
    def any(*specifiers):
        if len(specifiers) == 0:
            return AnySpecifier()

        if len(specifiers) == 1:
            return as_set(specifiers[0])
            
        return OrOperator(*[as_set(spec) for spec in specifiers])
    
    @staticmethod
    def invert(specifier):
        return NotOperator(as_set(specifier))

class NoneSpecifier(VersionSet):

    def allows_version(self, version):
        return False

    def __str__(self):
        return "none"

    def __repr__(self):
        return str(self)
        
class AnySpecifier(VersionSet):

    def allows_version(self, version):
        return True

    def __str__(self):
        return "any"

    def __repr__(self):
        return str(self)

class EqSpecifier(VersionSet):

    def __init__(self, version, original_string=None):
        self.version = version
        self.original_string = original_string

    def allows_version(self, version):
        return self.version == as_version(version)

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return f"{str(self.version)}"

    def __repr__(self):
        return f"{repr(self.version)}"

    def __hash__(self):
        return hash(("==", self.version))

class NotEqSpecifier(VersionSet):

    def __init__(self, version, original_string=None):
        self.version = version
        self.original_string = original_string

    def allows_version(self, version):
        return self.version != as_version(version)

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return f"!={str(self.version)}"

    def __repr__(self):
        return f"!={repr(self.version)}"

    def __hash__(self):
        return hash(("!=", self.version))

class GtEqSpecifier(VersionSet):

    def __init__(self, version, original_string=None):
        self.version = version
        self.original_string = original_string

    def allows_version(self, version):
        return as_version(version) >= self.version

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return f">={str(self.version)}"

    def __repr__(self):
        return f">={repr(self.version)}"

    def __hash__(self):
        return hash((">=", self.version))

class LtEqSpecifier(VersionSet):

    def __init__(self, version, original_string=None):
        self.version = version
        self.original_string = original_string

    def allows_version(self, version):
        return as_version(version) <= self.version

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return f"<={str(self.version)}"

    def __repr__(self):
        return f"<={repr(self.version)}"

    def __hash__(self):
        return hash(("<=", self.version))

class GtSpecifier(VersionSet):

    def __init__(self, version, original_string=None):
        self.version = version
        self.original_string = original_string

    def allows_version(self, version):
        return as_version(version) > self.version

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return f">{str(self.version)}"

    def __repr__(self):
        return f">{repr(self.version)}"

    def __hash__(self):
        return hash((">", self.version))

class LtSpecifier(VersionSet):

    def __init__(self, version, original_string=None):
        self.version = version
        self.original_string = original_string

    def allows_version(self, version):
        return as_version(version) < self.version

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return f"<{str(self.version)}"

    def __repr__(self):
        return f"<{repr(self.version)}"

    def __hash__(self):
        return hash(("<", self.version))

class AndOperator(VersionSet):

    def __init__(self, *specifiers, original_string=None):
        assert len(specifiers) > 0
        self.specifiers = specifiers
        self.original_string = original_string

    def allows_version(self, version):
        version = as_version(version)
        return all([spec.allows_version(version) for spec in self.specifiers])

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return "(" + " & ".join([str(spec) for spec in self.specifiers]) + ")"

    def __repr__(self):
        return "(" + " & ".join([repr(spec) for spec in self.specifiers]) + ")"

 
    def __hash__(self):
        return hash(("&", *self.specifiers))

class OrOperator(VersionSet):

    def __init__(self, *specifiers, original_string=None):
        assert len(specifiers) > 0
        self.specifiers = specifiers
        self.original_string = original_string

    def allows_version(self, version):
        version = as_version(version)
        return any([spec.allows_version(version) for spec in self.specifiers])

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return "(" + (" | ".join([str(spec) for spec in self.specifiers])) + ")"

    def __repr__(self):
        return "(" + (" | ".join([repr(spec) for spec in self.specifiers])) + ")"

 
    def __hash__(self):
        return hash(("|", *self.specifiers))

class NotOperator(VersionSet):

    def __init__(self, specifier, original_string=None):
        self.specifier = specifier
        self.original_string = original_string

    def allows_version(self, version):
        return not self.specifier.allows_version(as_version(version))

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return f"!{str(self.specifier)}"

    def __repr__(self):
        return f"!{repr(self.specifier)}"

    def __hash__(self):
        return hash(("!", self.specifier))


#
# Set parsing
#

AND = Literal("&") ^ Literal(",") ^ Literal("and")
OR = Literal("|") ^ Literal("or")
NOT = Literal("!")
EQ = Literal("==") #^ Literal("=")
NEQ = Literal("!=")
GT = Literal(">")
LT = Literal("<")
GTEQ = Literal(">=")
LTEQ = Literal("<=")

VERSION_STRING = Word(alphanums+".-+")


def parse_specifier(tokens):
    op, version = tokens
    
    if op == "==" or op == "=":
        return VersionSet.eq(version)

    if op == "!=":
        return VersionSet.neq(version)

    if op == ">":
        return VersionSet.gt(version)

    if op == "<":
        return VersionSet.lt(version)

    if op == ">=":
        return VersionSet.gteq(version)
    
    if op == "<=":
        return VersionSet.lteq(version)
    
    raise Exception(f"Unkown version specifier {op}")


SPECIFIER = ((EQ ^ NEQ ^ GT ^ LT ^ GTEQ ^ LTEQ ^ Empty().setParseAction(lambda x: "==")) + VERSION_STRING).setParseAction(parse_specifier)


def parse_not(tokens):
    return VersionSet.invert(tokens[0][1])

def parse_and(tokens):
    return VersionSet.all(*filter(lambda x: x not in ["&", ",", "and"], tokens[0]))

def parse_or(tokens):
    return VersionSet.any(*filter(lambda x: x not in ["|", "or"], tokens[0]))

TERM = ungroup(infixNotation(
    SPECIFIER,
    [
        (NOT, 1, opAssoc.RIGHT, parse_not),
        (AND, 2, opAssoc.LEFT, parse_and),
        (OR, 2, opAssoc.LEFT, parse_or),
        
    ]
))

def parse_version_set(string):
    return TERM.parseString(string, parseAll=True)[0]

#
# Requirement
#
REQUIREMENT_NAME = Word(alphanums+".-_")

REQUIREMENT = REQUIREMENT_NAME + TERM

class Requirement:

    def __init__(self, package_name, version_set, original_string=None):
        self.package_name = package_name
        self.version_set = version_set
        self.original_string = original_string

    @staticmethod
    def from_string(string):
        package_name, version_set = REQUIREMENT.parseString(string, parseAll=True)

        return Requirement(package_name, version_set, string)

    def __str__(self):
        if self.original_string is not None:
            return f"{self.original_string}"
        
        return f"{self.package_name} {self.version_set}"

    def __repr__(self):
        return f"{self.package_name} {self.version_set}"


#
# Maven Range parsing
#

VERSION_STRING = Word(alphanums+".-")

OPEN_RANGE = (Literal("(") ^ Literal("[")).setResultsName("include_min").setParseAction(lambda x: x[0] == "[")
MIN_VERSION = (VERSION_STRING ^ Empty()).setResultsName("min_version").setParseAction(lambda x: x if len(x) > 0 else "") 
MAX_VERSION = (VERSION_STRING ^ Empty()).setResultsName("max_version").setParseAction(lambda x: x if len(x) > 0 else "")
CLOSE_RANGE = (Literal(")") ^ Literal("]")).setResultsName("include_max").setParseAction(lambda x: x[0] == "]") 

VERSION_RANGE = Group(OPEN_RANGE + MIN_VERSION + Literal(",").suppress() + MAX_VERSION + CLOSE_RANGE)

MAVEN_VERSION_SET = delimitedList(Group(VERSION_STRING.setResultsName("version") ^ VERSION_RANGE.setResultsName("range")))


def parse_maven_version_set(requirement_string):
    result = MAVEN_VERSION_SET.parseString(requirement_string, parseAll=True)

    specifiers = []

    for res in result:
        if "range" in res:
            rng = []
            
            if "min_version" in res["range"]:
                if res["range"]["include_min"]:
                    rng.append(VersionSet.gteq(Version(res["range"]["min_version"])))
                else:
                    rng.append(VersionSet.gt(Version(res["range"]["min_version"])))
            
            if "max_version" in res["range"]:
                if res["range"]["include_max"]:
                    rng.append(VersionSet.lteq(Version(res["range"]["max_version"])))
                else:
                    rng.append(VersionSet.lt(Version(res["range"]["max_version"])))

            v = VersionSet.all(*rng)

        elif "version" in res:
            v = VersionSet.eq(Version(res["version"]))

        specifiers.append(v)
    
    return VersionSet.any(*specifiers)

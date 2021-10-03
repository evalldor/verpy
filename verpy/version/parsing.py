
from pyparsing import (
    Literal,
    CaselessLiteral,
    ParseException,
    Word, 
    Empty, 
    alphanums, 
    delimitedList, 
    Group, 
    nums, 
    alphas, 
    OneOrMore, 
    Optional, 
    infixNotation, 
    opAssoc, 
    ungroup
)

from . import types

#
# Version parsing
#
"""
'-' and transition between digits and character constitues a component boundary. 
'.' separates items within a component
"""
NUMERIC_PART = Word(nums+".").setParseAction(lambda x: types.NumericComponent(x[0]))
STRING_PART = Word(alphas+".").setParseAction(lambda x: types.StringComponent(x[0]))
COMPONENT = NUMERIC_PART ^ STRING_PART
SEPARATOR = Literal("-").suppress()
SECTION = COMPONENT ^ SEPARATOR
PREFIX = Optional(CaselessLiteral("v") ^ CaselessLiteral("ver") ^ CaselessLiteral("version")).suppress()

VERSION_PATTERN = PREFIX + OneOrMore(SECTION)

def parse_version(string):
    components = VERSION_PATTERN.parseString(string, parseAll=True)

    return types.Version(components, string)


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

    version = parse_version(version)
    
    if op == "==" or op == "=":
        return types.VersionSet.eq(version)

    if op == "!=":
        return types.VersionSet.neq(version)

    if op == ">":
        return types.VersionSet.gt(version)

    if op == "<":
        return types.VersionSet.lt(version)

    if op == ">=":
        return types.VersionSet.gteq(version)
    
    if op == "<=":
        return types.VersionSet.lteq(version)
    
    raise Exception(f"Unkown version specifier {op}")


SPECIFIER = ((EQ ^ NEQ ^ GT ^ LT ^ GTEQ ^ LTEQ ^ Empty().setParseAction(lambda x: "==")) + VERSION_STRING).setParseAction(parse_specifier)


def parse_not(tokens):
    return types.VersionSet.invert(tokens[0][1])

def parse_and(tokens):
    return types.VersionSet.all(*filter(lambda x: x not in ["&", ",", "and"], tokens[0]))

def parse_or(tokens):
    return types.VersionSet.any(*filter(lambda x: x not in ["|", "or"], tokens[0]))

VERSION_SET_PATTERN = ungroup(infixNotation(
    SPECIFIER,
    [
        (NOT, 1, opAssoc.RIGHT, parse_not),
        (AND, 2, opAssoc.LEFT, parse_and),
        (OR, 2, opAssoc.LEFT, parse_or),
        
    ]
))

def parse_version_set(string):
    try:
        return VERSION_SET_PATTERN.parseString(string, parseAll=True)[0]
    except ParseException as e:
        raise Exception(f"Error when parsing version set: {e.line}") from e



#
# Requirement
#
REQUIREMENT_NAME = Word(alphanums+".-_")

FLAGS = Group(Optional(Literal("[").suppress() + delimitedList(Word(alphanums+"-_")) + Literal("]").suppress()))

REQUIREMENT_PATTERN = REQUIREMENT_NAME + FLAGS + VERSION_SET_PATTERN

def parse_requirement(string):
    package_name, flags, version_set = REQUIREMENT_PATTERN.parseString(string, parseAll=True)

    return types.Requirement(package_name, version_set, flags, original_string=string)

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
                    rng.append(types.VersionSet.gteq(parse_version(res["range"]["min_version"])))
                else:
                    rng.append(types.VersionSet.gt(parse_version(res["range"]["min_version"])))
            
            if "max_version" in res["range"]:
                if res["range"]["include_max"]:
                    rng.append(types.VersionSet.lteq(parse_version(res["range"]["max_version"])))
                else:
                    rng.append(types.VersionSet.lt(parse_version(res["range"]["max_version"])))

            v = types.VersionSet.all(*rng)

        elif "version" in res:
            v = types.VersionSet.eq(parse_version(res["version"]))

        specifiers.append(v)
    
    return types.VersionSet.any(*specifiers)




#
# Python specific
#

import pkg_resources

def parse_python_version(string):
    return pkg_resources.parse_version(string)

def parse_python_version_set(string):
    pass

def parse_python_requirement(string):
    return next(pkg_resources.parse_requirements(string))
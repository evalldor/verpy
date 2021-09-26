import itertools

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

    def __init__(self, components, original_string=None):
        self.original_string = original_string
        self.components = components

    def __gt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented

        return compare_versions(self.components, other.components) > 0

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented

        return compare_versions(self.components, other.components) < 0

    def __ge__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
            
        return compare_versions(self.components, other.components) >= 0

    def __le__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
            
        return compare_versions(self.components, other.components) <= 0

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
            
        return compare_versions(self.components, other.components) == 0

    def __ne__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
            
        return compare_versions(self.components, other.components) != 0

    def __str__(self):
        if self.original_string is not None:
            return self.original_string

        return repr(self)

    def __repr__(self):
        return "-".join([str(c) for c in self.components])

    def __hash__(self):
        return hash(tuple(itertools.chain([c.normalized_representation() for c in self.components])))


class NumericComponent:

    def __init__(self, num_string):
        self.items = [int(i) for i in num_string.split(".") if i is not None and len(i) > 0]

    def __str__(self):
        return ".".join([str(i) for i in self.items])
    
    def __repr__(self):
        return str(self)

    def normalized_representation(self):
        """Used when hashing"""
        leading_non_zero_items = []

        for i in self.items:
            if i == 0:
                break
            leading_non_zero_items.append(i)

        return tuple(leading_non_zero_items)

    def __hash__(self):
        return hash(self.normalized_representation())


class StringComponent:

    def __init__(self, string):
        self.item = str(string).strip(". ")

    def normalized_representation(self):
        """Used when hashing"""
        return tuple([str(self).lower()])

    def __str__(self):
        return self.item
    
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
        l = max(len(a.items), len(b.items))
        
        a_items = [*a.items]
        while len(a_items) < l:
            a_items.append(0)

        b_items = [*b.items]
        while len(b_items) < l:
            b_items.append(0)
        
        for a_item, b_item in zip(a_items, b_items):
            if a_item > b_item:
                return GREATER
            if a_item < b_item:
                return LESSER

        return EQUAL

    elif isinstance(a, StringComponent) and isinstance(b, StringComponent):

        a_item = a.item.lower()
        b_item = b.item.lower()
    
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
        a_item = a.item.lower()
        if a_item in string_version_orderings:
            if string_version_orderings[a_item] > string_version_orderings[""]:
                return GREATER

            if string_version_orderings[a_item] < string_version_orderings[""]:
                return LESSER

            return EQUAL #Should never happend, but just to be safe..
        
        return LESSER
    
    raise Exception("Internal Error.")


class VersionSet:
    
    def __contains__(self, version):
        return self.contains(version)

    def union(self, specifier):
        return OrOperator(self, specifier)

    def intersection(self, specifier):
        return AndOperator(self, specifier)
    
    def complement(self):
        return NotOperator(self)

    def difference(self, specifier):
        return self.intersection(specifier).complement()

    def contains(self, version):
        #This method is implemented in the subclasses.
        raise NotImplementedError()

    @staticmethod
    def eq(version):
        return EqSpecifier(version)

    @staticmethod
    def neq(version):
        return NotEqSpecifier(version)

    @staticmethod
    def gteq(version):
        return GtEqSpecifier(version)

    @staticmethod
    def lteq(version):
        return LtEqSpecifier(version)

    @staticmethod
    def gt(version):
        return GtSpecifier(version)

    @staticmethod
    def lt(version):
        return LtSpecifier(version)
    
    @staticmethod
    def empty():
        return EmptySpecifier()

    @staticmethod
    def all(*specifiers):
        if len(specifiers) == 1:
            return specifiers[0]

        return AndOperator(*specifiers)
    
    @staticmethod
    def any(*specifiers):
        if len(specifiers) == 0:
            return AnySpecifier()

        if len(specifiers) == 1:
            return specifiers[0]
            
        return OrOperator(*specifiers)
    
    @staticmethod
    def invert(specifier):
        return NotOperator(specifier)


class EmptySpecifier(VersionSet):

    def contains(self, version):
        return False

    def __str__(self):
        return "none"

    def __repr__(self):
        return str(self)


class AnySpecifier(VersionSet):

    def contains(self, version):
        return True

    def __str__(self):
        return "any"

    def __repr__(self):
        return str(self)


class EqSpecifier(VersionSet):

    def __init__(self, version, original_string=None):
        self.version = version
        self.original_string = original_string

    def contains(self, version):
        return self.version == version

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

    def contains(self, version):
        return self.version != version

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

    def contains(self, version):
        return version >= self.version

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

    def contains(self, version):
        return version <= self.version

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

    def contains(self, version):
        return version > self.version

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

    def contains(self, version):
        return version < self.version

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

    def contains(self, version):
        return all([spec.contains(version) for spec in self.specifiers])

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

    def contains(self, version):
        return any([spec.contains(version) for spec in self.specifiers])

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

    def contains(self, version):
        return not self.specifier.contains(version)

    def __str__(self):
        if self.original_string is not None:
            return self.original_string
        
        return f"!{str(self.specifier)}"

    def __repr__(self):
        return f"!{repr(self.specifier)}"

    def __hash__(self):
        return hash(("!", self.specifier))


class Requirement:

    def __init__(self, package_name, version_set, original_string=None):
        self.package_name = package_name
        self.version_set = version_set
        self.original_string = original_string

    def __str__(self):
        if self.original_string is not None:
            return f"{self.original_string}"
        
        return f"{self.package_name} {self.version_set}"

    def __repr__(self):
        return f"{self.package_name} {self.version_set}"

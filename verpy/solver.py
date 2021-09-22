import sys
import collections
import itertools
import logging
import typing
from verpy.version.versioning import Version

from . import version as verpy

logger = logging.getLogger("solver")



def unique_items(items):
    seen = []

    for item in items:
        if item not in seen:
            seen.append(item)
            yield item





class NoAllowedVersionsCause:

    def __init__(self, package_name, violated_clauses) -> None:
        self.package_name = package_name
        self.violated_clauses = violated_clauses

    def __str__(self) -> str:
        return f"NoAllowedVersions(package_name={self.package_name}, violated_clauses={self.violated_clauses})"


class SolverError(Exception):
    pass


class PackageRepository:

    def get_versions(self, package_name):
        raise NotImplementedError()

    def get_dependencies(self, package_name, package_version) -> typing.List[verpy.Requirement]:
        raise NotImplementedError()


class DictRepository(PackageRepository):

    def __init__(self, contents) -> None:
        self.contents = {}
        
        for pkg_name, pkg_data in contents.items():
            self.contents[pkg_name] = {}
            for version, requirements in pkg_data.items():
                self.contents[pkg_name][verpy.version(version)] = [verpy.requirement(req) for req in requirements]

    def get_versions(self, package_name):
        return list(self.contents[package_name].keys())

    def get_dependencies(self, package_name, package_version):
        return list(self.contents[package_name][package_version])


class VersionSelectionStrategy:
    
    def get_prioritized_assignments(self, state, package_name):
        raise NotImplementedError()


class DefaultVersionSelectionStrategy(VersionSelectionStrategy):

    def get_prioritized_assignments(self, state, package_name):
        return [Assignment(package_name, version) for version in sorted(state.get_versions(package_name), reverse=True)]


class MavenVersionSelectionStrategy(VersionSelectionStrategy):

    def get_prioritized_assignments(self, state, package_name):
        # Chooses the highest version allowed by the requirement found closest
        # to root

        all_dependants = state.get_dependants(package_name)


        topmost_dependant = None    
        topmost_depth = sys.maxsize

        for dependant in all_dependants:
            depth = state.get_assignment_depth(dependant)

            if depth < topmost_depth:
                topmost_depth = depth
                topmost_dependant = dependant

        all_versions = sorted(state.get_versions(package_name), reverse=True)
        version_to_use = None
        for clause in state.clauses:
            if isinstance(clause, Dependency) and clause.dependant == topmost_dependant and clause.dependency.package_name == package_name:
                for version in all_versions:
                    if version in clause.dependency:
                        version_to_use = version
                        break

        if version_to_use is None:
            return []

        return Assignment(package_name, version_to_use, force=True)


class Assignment:

    def __init__(self, package_name: str, version: verpy.Version, force: bool = False) -> None:
        self.package_name = package_name
        self.version = version
        self.force = force

    def as_requirement(self):
        return verpy.Requirement(self.package_name, verpy.VersionSet.eq(self.version))

    def __str__(self) -> str:
        return f"{self.package_name} {self.version}"

    def __repr__(self) -> str:
        return str(self)
    
    def __hash__(self) -> int:
        return hash(("Assignment", self.package_name, self.version))

    def __eq__(self, other) -> bool:
        return hash(self) == hash(other)


class NullAssignment(Assignment):

    def __init__(self, package_name: str) -> None:
        super().__init__(package_name, None)


class RootAssignment(Assignment):

    def __init__(self) -> None:
        super().__init__("__root__", "1.0")


class Term:

    def __init__(self, requirement, polarity=True) -> None:
        self.requirement = requirement
        self.polarity = polarity

    @property
    def package_name(self) -> str:
        return self.requirement.package_name
    
    @property
    def version_set(self) -> verpy.VersionSet:
        return self.requirement.version_set

    def truth_value(self, assignments) -> typing.Union[bool, None]:
        for assignment in assignments:
            if assignment.package_name == self.package_name:
                if self.polarity:
                    return assignment.force or (not isinstance(assignment, NullAssignment) and assignment.version in self.version_set)
                
                return isinstance(assignment, NullAssignment) or assignment.version not in self.version_set
        
        return None

    def __str__(self) -> str:
        if self.polarity:
            return f"{self.requirement}"
        
        return f"not {self.requirement}"

    def __repr__(self) -> str:
        return str(self)


class Clause:

    def __init__(self, terms: typing.List[Term]) -> None:
        self.terms = terms

    def truth_value(self, assignments) -> typing.Union[bool, None]:
        for term in self.terms:
            truth_value = term.truth_value(assignments)
            
            if truth_value is True:
                return True

            if truth_value is None:
                return None

        return False

    def get_package_names(self) -> typing.List[str]:
        return list(unique_items([term.package_name for term in self.terms]))

    def __len__(self) -> int:
        return len(self.terms)

    def __iter__(self) -> Term:
        for term in self.terms:
            yield term

    def __str__(self) -> str:
        return " or ".join([str(term) for term in self.terms])

    def __repr__(self) -> str:
        return str(self)


class Dependency(Clause):

    def __init__(self, dependant: Assignment, dependency: verpy.Requirement) -> None:
        super().__init__([Term(dependant.as_requirement(), polarity=False), Term(dependency)])

        # These are stored here as shorthands to simplify dependency/dependant
        # lookups
        self.dependant = dependant
        self.dependency = dependency

class Incompatibility(Clause):

    def __init__(self, package_name, violated_clauses) -> None:
        super().__init__([term for term in unique_items(itertools.chain(*violated_clauses)) if term.package_name != package_name])

        self.package_name = package_name
        self.violated_clauses = violated_clauses

class SearchState:
    """Used by the solver to hold relevant state during the search
    """

    def __init__(self, repo : PackageRepository) -> None:
        self.repo = repo
        self.assignment_memory : typing.List[Assignment] = []
        self.clauses : typing.List[Clause] = []
        self.assignments : typing.List[Assignment] = []

    def add_root_dependencies(self, *requirements) -> None:
        root_assignment = RootAssignment()

        # This clause forces to root package to be selected. Otherwise the
        # solver would simply unassign root and be done.
        self.clauses.append(Clause([Term(root_assignment.as_requirement())]))

        self.assignments.append(root_assignment)

        for requirement in requirements:
            self.clauses.append(Dependency(root_assignment, requirement))

    def add_assignment(self, assignment) -> None:
        assert not self.has_assignment(assignment.package_name)

        self.assignments.append(assignment)
        
        self.load_dependencies(assignment)

    def has_assignment(self, package_name) -> bool:
        return self.get_assignment(package_name) != None

    def get_assignment(self, package_name) -> bool:
        for assignment in self.assignments:
            if assignment.package_name == package_name:
                return assignment
        
        return None

    def load_dependencies(self, assignment) -> typing.List[verpy.Requirement]:
        if not isinstance(assignment, NullAssignment) and assignment not in self.assignment_memory:
            self.assignment_memory.append(assignment)
            dependencies = self.repo.get_dependencies(assignment.package_name, assignment.version)

            for requirement in dependencies:
                self.clauses.append(Dependency(assignment, requirement))

    def get_versions(self, package_name) -> typing.List[verpy.Version]:
        return self.repo.get_versions(package_name)
    
    def get_dependants(self, package_name):
        dependants = []
        for clause in self.clauses:
            if isinstance(clause, Dependency) and clause.dependant in self.assignments and clause.dependency.package_name == package_name:
                dependants.append(clause.dependant)
        
        return dependants

    def get_dependencies_assignments(self, assignment):
        dependency = []
        for clause in self.clauses:
            if isinstance(clause, Dependency) and clause.dependant == assignment and clause.dependency in self.assignments:
                dependency.append(clause.dependant)
        
        return dependency

    def get_assignment_depth(self, assignment):
        if isinstance(assignment, RootAssignment):
            return 0
        
        dependant_assignments = self.get_dependants(assignment.package_name)
        depths = [self.get_assignment_depth(dependant)+1 for dependant in dependant_assignments]

        return min(depths)

    def backtrack(self, assignment) -> None:
        # Remove assignment and assignments for all dependencies
        dependencies = self.get_dependencies_assignments(assignment)
    
        for dependency in dependencies:
            self.backtrack(dependency)

        if not isinstance(assignment, RootAssignment):
            self.assignments.remove(assignment)

    def solution_is_complete(self) -> bool:

        for clause in self.clauses:
            if not clause.truth_value(self.assignments):
                return False
        
        return True

    def get_deepest_assignment_involving(self, package_names):
        deepest = None
        max_depth = -1
        for assignment in self.assignments:
            if assignment.package_name in package_names:
                depth = self.get_assignment_depth(assignment)
                if depth >= max_depth:
                    max_depth = depth
                    deepest = assignment

        return deepest

    def get_unassigned_packages(self):
        package_names = []
        
        for clause in self.clauses:
            for package_name in clause.get_package_names():
                if not self.has_assignment(package_name):
                    package_names.append(package_name)

        return list(unique_items(package_names))

    def get_current_solution(self):
        solution = {}

        for assignment in self.assignments:
            if not isinstance(assignment, (RootAssignment, NullAssignment)):
                solution[assignment.package_name] = str(assignment.version)

        return solution

    def has_failed(self):
        for clause in self.clauses:
            if clause.truth_value([self.assignments[0]]) is False:
                return True

        return False


def solve_dependencies(
    root_dependencies: typing.List[verpy.Requirement], 
    package_repository: PackageRepository, 
    version_selection_strategy: VersionSelectionStrategy = None
):

    # TODO: 
    # * Error reporting

    if version_selection_strategy is None:
        version_selection_strategy = DefaultVersionSelectionStrategy()

    state = SearchState(package_repository)

    state.add_root_dependencies(*root_dependencies)

    while not state.solution_is_complete():

        if state.has_failed():
            report_error(state)

        logger.debug("="*80)
        logger.debug(f"All assignments are: {state.assignments}")
        logger.debug(f"Unassigned packages are: {state.get_unassigned_packages()}")


        package_name = state.get_unassigned_packages()[0]
        logger.debug(f"Looking at package {package_name}:")


        all_versions = state.get_versions(package_name)
        logger.debug(f"\tAvailable versions are: {all_versions}:")

        # Try assigning a version to the package and see if that violates any
        # clauses. If if does, we move on to the next version etc. The order
        # that the versions are tried is determined by the version_selection_strategy

        all_violated_clauses = []
        assignment_to_make = None

        for assignment_to_try in [NullAssignment(package_name), *version_selection_strategy.get_prioritized_assignments(state, package_name)]:
            
            state.load_dependencies(assignment_to_try)
    
            assignments = [assignment_to_try] + state.assignments

            violated_clauses = [clause for clause in state.clauses if clause.truth_value(assignments) is False]
            
            if len(violated_clauses) == 0:
                assignment_to_make = assignment_to_try
                break
            
            all_violated_clauses.extend(violated_clauses)


        clauses = [clause for clause in state.clauses if package_name in clause.get_package_names()]
        
        logger.debug(f"\tRelevant clauses are:")
        for clause in clauses:
            logger.debug(f"\t\t{clause}")


        if assignment_to_make is None:
            # We have a conflict
            incompatibility = Incompatibility(package_name, unique_items(all_violated_clauses))

            logger.debug(f"\tConflict: no allowed versions! Created incompatibility {incompatibility}.")
            
            state.clauses.append(incompatibility)
            
            state.backtrack(state.get_deepest_assignment_involving(incompatibility.get_package_names()))

        else:
            logger.debug(f"\tAssigning version {assignment_to_make.version} to {package_name}.")
            state.add_assignment(assignment_to_make)


    return state.get_current_solution()


def _simplify_clause(clause : Clause) -> Clause:
    terms = collections.defaultdict(list)

    for term in clause:
        terms[term.package_name].append(term)
    
    simplified_terms = []

    for pkg_name, pkg_terms in terms.items():
        if len(pkg_terms) > 1:
            version = verpy.union(*[term.version_set for term in pkg_terms])
            simplified_terms.append(Term(verpy.Requirement(pkg_name, version)))
        else:
            simplified_terms.append(pkg_terms[0])

    return Clause(simplified_terms)


def _simplify_term(term : Term, all_versions: typing.List[verpy.Version]) -> Term:
    pass


def report_error(state: SearchState):

    root_clause = None
    for clause in state.clauses:
        if clause.truth_value([state.assignments[0]]) is False:
            root_clause = clause
            break

    _dump_conflict(root_clause)
    
    raise SolverError()

def _dump_conflict(clause):

    print(clause)
    if isinstance(clause, Incompatibility):
        for _clause in clause.violated_clauses:
            _dump_conflict(_clause)

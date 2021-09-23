import sys
import collections
import itertools
import logging
import typing

from . import version as verpy

logger = logging.getLogger("solver")


def unique_items(items):
    seen = []

    for item in items:
        if item not in seen:
            seen.append(item)
            yield item


class SolverError(Exception):
    
    def __init__(self, package_name, conflicting_requirements, root_requirements_involved) -> None:
        self.package_name = package_name
        self.conflicting_requirements = conflicting_requirements
        self.root_requirements_involved = root_requirements_involved


class PackageRepository:

    def get_versions(self, package_name) -> typing.List[verpy.Version]:
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

        all_dependants = state.get_dependant_assignments(package_name)


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

        return [Assignment(package_name, version_to_use, force=True)]


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
    """A Term contains a statement (requirement) about a package. It is
    evaluated to True when an assignment satisfies the requirement.
    """

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
    """A Clause is a disjuction of a set of Terms. It is evaluated to True when
    at least one of the terms is True.
    """

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
        
        # Contains the list of all clauses added during the search. The search
        # is complete when all clauses in this list evaluates to True under the
        # current list of assignments.
        self.clauses : typing.List[Clause] = []

        # Contains the list of all current assignments (an assignment maps a
        # package name to a version). It changes constantly during search, but
        # when the search is complete, this list is the solution.
        self.assignments : typing.List[Assignment] = []

        # Caches
        self.loaded_dependencies : typing.List[Assignment] = []
        self.available_versions : typing.Mapping[str, typing.List[verpy.Version]] = {}

    def add_root_dependencies(self, *requirements) -> None:
        root_assignment = RootAssignment()

        self.assignments.append(root_assignment)

        for requirement in requirements:
            self.clauses.append(Dependency(root_assignment, requirement))

    def add_assignment(self, assignment) -> None:
        self.assignments.append(assignment)
        self.load_dependencies(assignment)

    def has_assignment(self, package_name) -> bool:
        for assignment in self.assignments:
            if assignment.package_name == package_name:
                return True
        
        return False

    def load_dependencies(self, assignment) -> typing.List[verpy.Requirement]:
        if not isinstance(assignment, NullAssignment) and assignment not in self.loaded_dependencies:
            self.loaded_dependencies.append(assignment)
            dependencies = self.repo.get_dependencies(assignment.package_name, assignment.version)

            for requirement in dependencies:
                self.clauses.append(Dependency(assignment, requirement))

    def get_versions(self, package_name) -> typing.List[verpy.Version]:
        if package_name not in self.available_versions:
            self.available_versions[package_name] = self.repo.get_versions(package_name)

        return self.available_versions[package_name]
    
    def get_dependant_assignments(self, package_name):
        dependants = []
        for clause in self.clauses:
            if isinstance(clause, Dependency) and clause.dependant in self.assignments and clause.dependency.package_name == package_name:
                dependants.append(clause.dependant)
        
        return dependants

    def get_dependency_assignments(self, assignment):
        dependency = []
        for clause in self.clauses:
            if isinstance(clause, Dependency) and clause.dependant == assignment and clause.dependency in self.assignments:
                dependency.append(clause.dependant)
        
        return dependency

    def get_assignment_depth(self, assignment):
        if isinstance(assignment, RootAssignment):
            return 0
        
        dependant_assignments = self.get_dependant_assignments(assignment.package_name)
        depths = [self.get_assignment_depth(dependant)+1 for dependant in dependant_assignments]

        return min(depths)

    def backtrack(self, assignment) -> None:
        # Remove assignment and assignments for all dependencies
        dependencies = self.get_dependency_assignments(assignment)
    
        for dependency in dependencies:
            self.backtrack(dependency)

        if not isinstance(assignment, RootAssignment):
            self.assignments.remove(assignment)

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
        assigned_package_names = [a.package_name for a in self.assignments]
        unassigned_package_names = []
        
        for package_name in unique_items(itertools.chain(*[clause.get_package_names() for clause in self.clauses])):
            if package_name not in assigned_package_names:
                unassigned_package_names.append(package_name)

        return unassigned_package_names

    def get_current_solution(self):
        solution = {}

        for assignment in self.assignments:
            if not isinstance(assignment, (RootAssignment, NullAssignment)):
                solution[assignment.package_name] = str(assignment.version)

        return solution
    
    def is_solution_complete(self) -> bool:
        for clause in self.clauses:
            if not clause.truth_value(self.assignments):
                return False
        
        return True

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

    while not state.is_solution_complete():

        if state.has_failed():
            raise create_error(state)

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
            
            for clause in violated_clauses:
                if clause not in all_violated_clauses:
                    all_violated_clauses.append(clause)


        # Some debug printing
        clauses = [clause for clause in state.clauses if package_name in clause.get_package_names()]
        logger.debug(f"\tRelevant clauses are:")
        for clause in clauses:
            logger.debug(f"\t\t{clause}")


        if assignment_to_make is None:
            # We have a conflict
            incompatibility = Incompatibility(package_name, all_violated_clauses)

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


def create_error(state: SearchState):

    # Find incompatibility that has only Dependencies as its cause. This is the
    # root if the conflict.

    root_incompatibility = None
    for clause in state.clauses:
        if clause.truth_value([state.assignments[0]]) is False:
            root_incompatibility = clause
            break
    
    root_clause = find_root_cause(root_incompatibility)
    
    package_name = root_clause.package_name
    conflicting_requirements = []
    
    for clause in root_clause.violated_clauses:
        conflicting_requirements.append(clause)

    root_requirements_involved = []

    for clause in root_incompatibility.violated_clauses:
        for term in clause:
            if term.package_name != "__root__":
                root_requirements_involved.append(term.requirement)
    

    # print(f"Unable to find a matching version for package '{root_clause.package_name}' because:")
    # dependency_strings = [f"{clause.dependant} requires {clause.dependency}" for clause in root_clause.violated_clauses]
    # print("\t" + " and \n\t".join(dependency_strings))
    # print(f"which are mutually incompatible requirements!")

    return SolverError(
        package_name=package_name,
        conflicting_requirements=conflicting_requirements,
        root_requirements_involved=root_requirements_involved
    )


def find_root_cause(clause):
    if isinstance(clause, Incompatibility):
        results = [find_root_cause(c) for c in clause.violated_clauses]
        for result in results:
            if result is not False:
                return result

        return clause


    return False

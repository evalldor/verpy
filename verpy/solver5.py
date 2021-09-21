import collections
import copy
import itertools
import logging
import typing

from . import version as verpy

logger = logging.getLogger("solver")


class Cause:
    pass


class DependencyCause(Cause):
    pass


class IncompatibilityCause(Cause):
    pass


class SolverError(Exception):
    pass


class Repository:

    def get_versions(self, package_name):
        raise NotImplementedError()

    def get_dependencies(self, package_name, package_version) -> typing.List[verpy.Requirement]:
        raise NotImplementedError()


class DictRepository(Repository):

    def __init__(self, contents) -> None:
        self.contents = {}
        
        for pkg_name, pkg_data in contents.items():
            self.contents[pkg_name] = {}
            for version, requirements in pkg_data.items():
                self.contents[pkg_name][verpy.version(version)] = [verpy.requirement(req) for req in requirements]

    def get_versions(self, package_name):
        return sorted(self.contents[package_name].keys(), reverse=True) # Latest version first

    def get_dependencies(self, package_name, package_version):
        return list(self.contents[package_name][package_version])


class Assignment:

    def __init__(self, package_name: str, version: verpy.Version) -> None:
        self.package_name = package_name
        self.version = version

    def as_requirement(self):
        return verpy.Requirement(self.package_name, verpy.VersionSet.eq(self.version))

    def as_complement_requirement(self):
        return verpy.Requirement(self.package_name, verpy.VersionSet.eq(self.version).complement())

    def __str__(self) -> str:
        return f"{self.package_name} {self.version}"

    def __repr__(self) -> str:
        return str(self)
    
    def __hash__(self) -> int:
        return hash(("Assignment", self.package_name, self.version))

    def __eq__(self, other) -> bool:
        return hash(self) == hash(other)


class RootAssignment(Assignment):

    def __init__(self) -> None:
        super().__init__("__root__", "1.0")


class Term:

    def __init__(self, requirement) -> None:
        self.requirement = requirement

    @property
    def package_name(self) -> str:
        return self.requirement.package_name
    
    @property
    def version_set(self) -> verpy.VersionSet:
        return self.requirement.version_set

    def truth_value(self, assignments) -> typing.Union[bool, None]:
        for assignment in assignments:
            if assignment.package_name == self.package_name:
                return assignment.version in self.version_set
        
        return None

    def __str__(self) -> str:
        return f"{self.requirement}"

    def __repr__(self) -> str:
        return str(self)


class Clause:

    def __init__(self, terms: typing.List[Term], cause: Cause=None) -> None:
        self.terms = terms
        self.cause = cause

    def truth_value(self, assignments) -> bool:
        truth_values = [term.truth_value(assignments) for term in self.terms]

        if True in truth_values:
            return True
        
        if None in truth_values:
            return None
        
        return False

    def get_package_names(self) -> typing.List[str]:
        package_names = []

        for term in self.terms:
            if term.package_name not in package_names:
                package_names.append(term.package_name)

        return package_names

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
        super().__init__([Term(dependant.as_complement_requirement()), Term(dependency)], DependencyCause())

        # These are stored here as shorthands to simplify error reporting
        self.dependant = dependant
        self.dependency = dependency


class Incompatibility(Clause):

    def __init__(self, terms: typing.List[Term]) -> None:
        super().__init__(terms, IncompatibilityCause())


class SearchState:
    """Holds relevant state while the solver searches for a solution
    """

    def __init__(self, repo) -> None:
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
        if assignment.version != verpy.Version("none") and assignment not in self.assignment_memory:
            self.assignment_memory.append(assignment)
            dependencies = self.repo.get_dependencies(assignment.package_name, assignment.version)

            for requirement in dependencies:
                self.clauses.append(Dependency(assignment, requirement))

    def get_versions(self, package_name) -> typing.List[verpy.Version]:
        return self.repo.get_versions(package_name)
    
    def get_dependants(self, assignment):
        dependants = []
        for clause in self.clauses:
            if isinstance(clause, Dependency) and clause.dependency.package_name == assignment.package_name:
                if clause.dependant in self.assignments:
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
        
        dependant_assignments = self.get_dependants(assignment)
        depths = [self.get_assignment_depth(dependant)+1 for dependant in dependant_assignments]

        return min(depths)

    def backtrack(self, assignment) -> None:
        
        # Remove all assignments that depend on this assignment
        dependencies = self.get_dependencies_assignments(assignment)
    
        for dependency in dependencies:
            self.backtrack(dependency)

        self.assignments.remove(assignment)

    def solution_is_complete(self) -> bool:
        return all([clause.truth_value(self.assignments) for clause in self.clauses])

    def get_all_clauses_involving_package(self, package_name) -> typing.List[Clause]:
        clauses = []
        
        for clause in self.clauses:
            if package_name in clause.get_package_names():
                clauses.append(clause)

        return clauses

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
                if not self.has_assignment(package_name) and package_name not in package_names:
                    package_names.append(package_name)

        return package_names

    def get_unsatisfied_clauses(self):
        unsatisfied_clauses = []        
        
        for clause in self.clauses:
            if clause.truth_value(self.assignments) is False:
                unsatisfied_clauses.append(clause)

        return unsatisfied_clauses

    def get_current_solution(self):
        solution = {}

        for assignment in self.assignments:
            if not isinstance(assignment, RootAssignment) and assignment.version != verpy.Version("none"):
                solution[assignment.package_name] = str(assignment.version)

        return solution


def solve_dependencies(root_dependencies, package_repository):
    # TODO: 
    # * Version selection strategies
    

    state = SearchState(package_repository)

    state.add_root_dependencies(*root_dependencies)

    while not state.solution_is_complete():

        logger.debug("="*80)
        logger.debug(f"All assignments are: {state.assignments}")
        logger.debug(f"Unassigned packages are: {state.get_unassigned_packages()}")


        package_name = state.get_unassigned_packages()[0]
        logger.debug(f"Looking at package {package_name}:")


        all_versions = state.get_versions(package_name)
        logger.debug(f"\tAvailable versions are: {all_versions}:")


        all_violated_clauses = []
        version_to_assign = None

        for version in [verpy.Version("none"), *all_versions]:
            assignment_to_try = Assignment(package_name, version)

            violated_clauses = _try_assignment(state, assignment_to_try)
            
            if len(violated_clauses) == 0:
                version_to_assign = version
                break
            
            for clause in violated_clauses:
                if clause not in all_violated_clauses:
                    all_violated_clauses.append(clause)


        clauses = state.get_all_clauses_involving_package(package_name)
        logger.debug(f"\tRelevant clauses are:")
        for clause in clauses:
            logger.debug(f"\t\t{clause}")



        if version_to_assign is None:
            terms = []

            for clause in all_violated_clauses:
                for term in clause:
                    if term.package_name != package_name:
                        terms.append(term)

            incompatibility = Incompatibility(terms)

            logger.debug(f"\tNo allowed versions. Created incompatibility {incompatibility}")
            
            state.clauses.append(incompatibility)
            
            state.backtrack(state.get_deepest_assignment_involving(incompatibility.get_package_names()))
        
        elif state.has_assignment(package_name):
            
            assignment = state.get_assignment(package_name)
            logger.debug(f"\tFound existing assignment: {assignment}")
            

            if assignment.version != version_to_assign:
                logger.debug(f"\t\tThe existing assignment is not ok! Backtracking!")
                state.backtrack(assignment)
            else:
                assert False, "Should never happend"

        else:
            logger.debug(f"\tAssigning version {version_to_assign} to {package_name}.")
            state.add_assignment(Assignment(package_name, version_to_assign))


    return state.get_current_solution()


def _try_assignment(state: SearchState, assignment_to_try: Assignment):
    
    state.load_dependencies(assignment_to_try)
    
    relevant_clauses = state.get_all_clauses_involving_package(assignment_to_try.package_name)

    assignments_to_use = [assignment_to_try]
    for assignment in state.assignments:
        if assignment.package_name != assignment_to_try.package_name:
            assignments_to_use.append(assignment)

    violated_clauses = []
    for clause in relevant_clauses:
        if clause.truth_value(assignments_to_use) is False:
            violated_clauses.append(clause)
    
    return violated_clauses


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

import collections
from verpy.version.versioning import Requirement, as_requirement
from . import version as verpy
import itertools
import typing
import logging

import copy

logger = logging.getLogger("solver")


class SolverError(Exception):
    pass


class ConflictError(SolverError):
    pass


class NoAllowedVersionsError(SolverError):
    pass


class AllAssignmentsFailed(SolverError):
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


class Checkpoint:

    def __init__(self) -> None:
        self.assignments = []

    def append(self, assignment):
        self.assignments.append(assignment)


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

    def __init__(self, terms : typing.List[Term] ) -> None:
        assert len({term.package_name for term in terms}) == len(terms), "There may only be one term per package in a clause"

        self.terms = terms

    def truth_value(self, assignments) -> bool:
        truth_values = [term.truth_value(assignments) for term in self.terms]

        if True in truth_values:
            return True
        
        if None in truth_values:
            return None
        
        return False

    def get_package_names(self) -> typing.List[str]:
        return [term.package_name for term in self.terms]

    def __len__(self) -> int:
        return len(self.terms)

    def __iter__(self) -> Term:
        for term in self.terms:
            yield term

    def __str__(self) -> str:
        return " or ".join([str(term) for term in self.terms])

    def __repr__(self) -> str:
        return str(self)


class SearchState:

    def __init__(self, repo) -> None:
        self.repo = repo
        self.assignment_memory : typing.List[Assignment] = []
        self.clauses : typing.List[Clause] = []
        self.assignments : typing.List[Assignment] = []

    def add_root_dependencies(self, *requirements) -> None:
        root_assignment = RootAssignment()
        self.clauses.append(Clause([Term(root_assignment.as_requirement())]))
        self.assignments.append(root_assignment)

        for requirement in requirements:
            self.clauses.append(Clause([Term(root_assignment.as_complement_requirement()), Term(requirement)]))

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
                self.clauses.append(Clause([
                    Term(assignment.as_complement_requirement()),
                    Term(requirement)
                ]))

    def get_versions(self, package_name) -> typing.List[verpy.Version]:
        return self.repo.get_versions(package_name)
        
    def backtrack(self, assignment) -> None:
        index = self.assignments.index(assignment)
        self.assignments = self.assignments[:index]

    def solution_is_complete(self) -> bool:
        return all([clause.truth_value(self.assignments) for clause in self.clauses])

    def get_all_clauses_involving_package(self, package_name) -> typing.List[Clause]:
        clauses = []
        
        for clause in self.clauses:
            if package_name in clause.get_package_names():
                clauses.append(clause)

        return clauses

    def simplify(self, clauses: typing.List[Clause]) -> typing.List[Clause]:
        package_to_clause = collections.defaultdict(list)
        
        clauses_copy = copy.deepcopy(clauses)

        for clause in clauses_copy:
            for name in clause.get_package_names():
                package_to_clause[name].append(clause)

        for package_name in package_to_clause.keys():
            terms = []

            for clause in package_to_clause[package_name]:
                for term in clause:
                    if term.package_name == package_name:
                        terms.append(term)

    def get_latest_assignment_involving(self, package_names):
        for assignment in reversed(self.assignments):
            if assignment.package_name in package_names:
                return assignment

        return None

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

    def get_assignment_depth(self):
        pass

def solve_dependencies(root_dependencies, package_repository):
    # Add explicit assignments to packages that are not chosen, e.g. assigned
    # with version 'None'. Terms referencing a package that has no assignment
    # are inconclusive.

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

        if len(all_versions) == 0:
            exit(0)


        violated_clauses = []
        version_to_assign = None

        for version in [verpy.Version("none"), *all_versions]:
            assignment_to_try = Assignment(package_name, version)
            state.load_dependencies(assignment_to_try)

            v_clauses = _get_violated_clauses([assignment_to_try] + list(filter(lambda x: x.package_name != package_name, state.assignments)), state.get_all_clauses_involving_package(package_name))
            if len(v_clauses) > 0:
                violated_clauses.extend(v_clauses)
            else:
                version_to_assign = version
                break


        clauses = state.get_all_clauses_involving_package(package_name)
        logger.debug(f"\tRelevant clauses are:")
        for clause in clauses:
            logger.debug(f"\t\t{clause}")



        if version_to_assign is None:
            terms = collections.defaultdict(list)

            for clause in violated_clauses:
                for term in clause:
                    if term.package_name != package_name:
                        terms[term.package_name].append(term)
            
            all_terms = []

            for pkg_name, pkg_terms in terms.items():
                if len(pkg_terms) > 1:
                    version = verpy.union(*[term.version_set for term in pkg_terms])
                    all_terms.append(Term(verpy.Requirement(pkg_name, version)))
                else:
                    all_terms.append(pkg_terms[0])


            incompatibility = Clause(all_terms)
            logger.debug(f"\tNo allowed versions. Created incompatibility {incompatibility}")
            state.clauses.append(incompatibility)
            state.backtrack(state.get_latest_assignment_involving(incompatibility.get_package_names()))
        
        elif state.has_assignment(package_name):
            
            assignment = state.get_assignment(package_name)
            logger.debug(f"\tFound existing assignment: {assignment}")
            

            if assignment.version != version_to_assign:
                logger.debug(f"\t\tThe existing assignment is not ok! Backtracking!")
                state.backtrack(assignment)

        else:
            logger.debug(f"\tAssigning version {version_to_assign} to {package_name}.")
            state.add_assignment(Assignment(package_name, version_to_assign))


    return list(filter(lambda x: not isinstance(x, RootAssignment) and x.version != verpy.Version("none"), state.assignments))


def _get_violated_clauses(assignments, clauses):
    violated_clauses = []
    for clause in clauses:
        if clause.truth_value(assignments) is False:
            violated_clauses.append(clause)
    
    return violated_clauses

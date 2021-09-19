import collections
from verpy.version.versioning import Requirement
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
        super().__init__("__root__", "0")
    

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
                    return assignment.version is not None and assignment.version in self.version_set
                
                return assignment.version is None or assignment.version not in self.version_set
        
        return None

    def __str__(self) -> str:
        if self.polarity:
            return f"{self.requirement}"
        
        return f"not {self.requirement}"

    def __repr__(self) -> str:
        return str(self)


class Clause:

    def __init__(self, terms : typing.List[Term] ) -> None:
        assert (len({term.package_name for term in terms}) == len(terms), 
            "There may only be one term per package in a clause")

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

    def __str__(self) -> str:
        return " or ".join([str(term) for term in self.terms])

    def __repr__(self) -> str:
        return str(self)


class SearchState:

    def __init__(self, repo) -> None:
        self.repo = repo
        self.assignment_memory : typing.List[Assignment] = []
        self.clauses : typing.List[Clause] = []

        self.checkpoints : typing.List[Checkpoint] = [Checkpoint()]

    @property
    def assignments(self) -> typing.List[Assignment]:
        return list(itertools.chain(*[cp.assignments for cp in self.checkpoints]))

    def add_root_dependency(self, requirement) -> None:
        self.clauses.append(Clause([Term(requirement)]))

    def add_assignment(self, assignment) -> None:
        assert not self.has_assignment(assignment.package_name)

        self.checkpoints[-1].append(assignment)

        if assignment not in self.assignment_memory:
            self.assignment_memory.append(assignment)

            for requirement in self.get_dependencies(assignment):
                self.clauses.append(Clause([
                    Term(assignment.as_requirement(), polarity=False),
                    Term(requirement)
                ]))

    def has_assignment(self, package_name) -> bool:
        return self.get_assignment(package_name) != None

    def get_assignment(self, package_name) -> bool:
        for assignment in self.assignments:
            if assignment.package_name == package_name:
                return assignment
        
        return None

    def get_dependencies(self, assignment) -> typing.List[verpy.Requirement]:
        return self.repo.get_dependencies(assignment.package_name, assignment.version)

    def get_versions(self, package_name) -> typing.List[verpy.Version]:
        return self.repo.get_versions(package_name)
        
    def checkpoint(self) -> None:
        self.checkpoints.append(Checkpoint())

    def backtrack(self, assignment) -> None:
        checkpoint_to_restore = None
        for checkpoint in self.checkpoints:
            if assignment in checkpoint.assignments:
                checkpoint_to_restore = checkpoint

        assert checkpoint_to_restore is not None

        index = self.checkpoints.index(checkpoint_to_restore)
        self.checkpoints = self.checkpoints[:index]

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


def solve_dependencies(root_dependencies, package_repository):
    # Add explicit assignments to packages that are not chosen, e.g. assigned
    # with version 'None'. Terms referencing a package that has no assignment
    # are inconclusive.

    state = SearchState(package_repository)

    for requirement in root_dependencies:
        state.add_root_dependency(requirement)

    while not state.solution_is_complete():

        state.checkpoint()

        logger.debug(f"All assignments are: {state.assignments}")

        unsatisfied_clauses = []        
        package_name = None

        for clause in state.clauses:
            if not clause.truth_value(state.assignments):
                unsatisfied_clauses.append(clause)
                for term in clause.terms:
                    if term.polarity is True:
                        package_name = term.package_name

        logger.debug(f"Unsatisfied clauses are:")
        for clause in unsatisfied_clauses:
            logger.debug(f"\t\t{clause}")

        logger.debug(f"Looking at package {package_name}:")


        all_versions = state.get_versions(package_name)
        logger.debug(f"\tAvailable versions are: {all_versions}:")


        clauses = state.get_all_clauses_involving_package(package_name)
        logger.debug(f"\tRelevant clauses are:")
        for clause in clauses:
            logger.debug(f"\t\t{clause}")

        
        allowed_versions = _filter_allowed_version(state.assignments, clauses, package_name, all_versions)
        logger.debug(f"\tAllowed versions are: {allowed_versions}:")


        if len(allowed_versions) == 0:
            resolve_conflict()
        
        elif state.has_assignment(package_name):
            
            assignment = state.get_assignment(package_name)
            logger.debug(f"\tFound existing assignment: {assignment}")
            

            if assignment.version != allowed_versions[0]:
                logger.debug(f"\t\tThe existing assignment is not ok! Backtracking!")
                state.backtrack(assignment)
            else:
                exit(0)
        else:
            logger.debug(f"\tAssigning version {allowed_versions[0]} to {package_name}.")
            state.add_assignment(Assignment(package_name, allowed_versions[0]))


    return state.assignments



def _filter_allowed_version(assignments, clauses, package_name, all_versions):
    assignments = list(filter(lambda x: x.package_name != package_name, assignments))

    def allowed_version_filter(version):
        _assignments = assignments + [Assignment(package_name, version)]

        for clause in clauses:
            if clause.truth_value(_assignments) is False:
                return False
        
        return True

    return list(filter(allowed_version_filter, all_versions))


def resolve_conflict():
    pass


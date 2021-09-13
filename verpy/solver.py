import collections
import itertools
import typing
from . import version as verpy

import logging

logger = logging.getLogger("solver")

class Assignment:

    def __init__(self, package_name, version) -> None:
        self.package_name = package_name
        self.version = version

    def __hash__(self):
        return hash((self.package_name, self.version))

    def __str__(self) -> str:
        return f"{self.package_name} {self.version}"

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, o: object) -> bool:
        return hash(self) == hash(o)

class Incompatibility:

    def __init__(self, assignments) -> None:
        self.assignments = set(assignments)

    def is_subset_of(self, other):
        return self.assignments.issubset(other.assignments)
    
    def __str__(self) -> str:
        return " ".join([str(a) for a in self.assignments])

    def __repr__(self) -> str:
        return str(self)


class Conflict:

    def __init__(self, cause, effect) -> None:
        self.cause = cause
        self.effect = effect

    def is_satisfied_by(self, assignments):
        return self.cause.is_subset_of(Incompatibility(assignments))


class Constraint:

    def __init__(self, source, requirement) -> None:
        self.source = source
        self.package_name = requirement.package_name
        self.version_set = requirement.version_set

    def is_active_for(self, assignments):
        if isinstance(self.source, Assignment):
            return self.source in assignments
        
        if isinstance(self.source, Incompatibility):
            return self.source.is_subset_of(Incompatibility(assignments))

        assert False

    def is_violated_for(self, assignments):
        for assignment in assignments:
            if assignment.package_name == self.package_name:
                if assignment.version not in self.version_set:
                    return True
        
        return False

    def is_source_satisfied_by(self, assignments):
        if isinstance(self.source, Assignment):
            return self.source in assignments
        
        if isinstance(self.source, Incompatibility):
            return self.source.is_subset_of(Incompatibility(assignments))

        assert False

class Book2:
    def __init__(self, repo) -> None:
        self.repo = repo
        self.assignments = []
        self.constraints = []
        self.frontiers = []

    def get_active_constraints(self):
        pass

    def get_available_versions(self, package_name):
        return self.repo.get_versions(package_name)

    def get_allowed_versions(self, package_name):

        all_versions = self.get_available_versions(package_name)

        disallowed_versions = []

        for version in all_versions:
            for constraint in self.get_constraints(package_name):
                if constraint.is_source_satisfied_by(self.assignments + [Assignment(package_name, version)]):
                    if version not in constraint.version_set:
                        disallowed_versions.append(version)
         
        for ver in disallowed_versions:
            all_versions.remove(ver)

        return all_versions

    def get_assignment_for(self, package_name):
        
        for assignment in self.assignments:
            if assignment.package_name == package_name:
                return assignment
        
        return None

    def has_assignment(self, package_name):
        return self.get_assignment_for(package_name) is not None

    def get_constraints(self, package_name):
        
        constraints = []

        for constraint in self.constraints:
            if constraint.package_name == package_name:
                constraints.append(constraint)
        
        return constraints

    def get_dependency_constraints(self, package_name):
        constraints = []

        for constraint in self.get_active_constraints():
            if constraint.package_name == package_name and isinstance(constraint.source, Assignment):
                constraints.append(constraint)
        
        return constraints

    def get_non_dependency_constraints(self, package_name):
        constraints = []

        for constraint in self.get_active_constraints():
            if constraint.package_name == package_name and not isinstance(constraint.source, Assignment):
                constraints.append(constraint)
        
        return constraints

    def get_active_constraints(self, package_name, assignments=None):
        if assignments is None:
            assignments = self.assignments

        active_constraints = []

        for constraint in self.constraints:
            if constraint.package_name == package_name and constraint.is_source_satisfied_by(assignments):
                active_constraints.append(constraint)
        
        return active_constraints
    
    def remove_assignment(self, package_name):
        assignment = self.get_assignment_for(package_name)
        self.assignments.remove(assignment)

        constraints_to_remove = []

        for constraint in self.constraints:
            if constraint.source is assignment:
                constraints_to_remove.append(constraint)

                if constraint.package_name not in self.frontiers:
                    self.frontiers.insert(0, constraint.package_name)

        for constraint in constraints_to_remove:
            self.constraints.remove(constraint)
            
    def add_assignment(self, assignment, dependencies=None):
        
        assert not self.has_assignment(assignment.package_name)

        if dependencies is None:
            dependencies = self.repo.get_dependencies(assignment.package_name, assignment.version)
        
        self.assignments.append(assignment)

        for requirement in dependencies:
            self.constraints.append(Constraint(assignment, requirement))
            if requirement.package_name not in self.frontiers:
                self.frontiers.append(requirement.package_name)
    
    def add_constraint(self, constraint):
        self.constraints.append(constraint)
    
    def has_frontiers(self):
        return len(self.frontiers) > 0

    def pop_frontier(self):
        return self.frontiers.pop(0)

    def add_frontier(self, package_name):
        self.frontiers.append(package_name)

    def get_assignments(self):
        return self.assignments


class Book:

    def __init__(self, repo) -> None:
        self.repo = repo
        self.assignments = {}
        self.incompatibilities = []
        self.frontiers = []
        self.conflicts = []

    def get_available_versions(self, package_name):
        return self.repo.get_versions(package_name)

    def get_allowed_versions(self, package_name):
        requirements = self.get_requirements_on(package_name)
        intersection = verpy.intersection(*[req.version_set for req in requirements])
        allowed_versions = intersection.filter_allowed(self.get_available_versions(package_name))
        
        versions_with_conflicts = []
        for version in allowed_versions:
            for conflict in self.conflicts:
                if conflict.is_satisfied_by(self.get_assignments() + [Assignment(package_name, version)]):
                    versions_with_conflicts.append(version)
                    break


        for ver in versions_with_conflicts:
            allowed_versions.remove(ver)

        return allowed_versions

    def get_all_requirements_for_package(self, package_name):
        requirements = []

        for assignment, reqs in self.assignments.items():
            
            for req in reqs:
                if req.package_name == package_name:
                    requirements.append((assignment, req))

        return requirements

    def get_requirements_on(self, package_name):
        requirements = []

        for assignment, reqs in self.assignments.items():
            
            for req in reqs:
                if req.package_name == package_name:
                    requirements.append(req)

        return requirements

    def get_assignments(self):
        return list(self.assignments.keys())
    
    def get_assignment_for(self, package_name):
        
        for assignment in self.assignments.keys():
            if assignment.package_name == package_name:
                return assignment
        
        return None

    def has_assignment(self, package_name):
        return self.get_assignment_for(package_name) is not None

    def add_assignment(self, package_name, package_version, package_requirements=None):
        assignment = Assignment(package_name, package_version)
        if package_requirements is None:
            package_requirements = self.repo.get_dependencies(package_name, package_version)
        
        if self.has_assignment(package_name):
            raise ValueError(f"Assignment for {package_name} already exists!")

        self.assignments[assignment] = package_requirements

        for requirement in package_requirements:
            if requirement.package_name not in self.frontiers:
                self.frontiers.append(requirement.package_name)

    def remove_assignment(self, package_name):
        ass = self.get_assignment_for(package_name)
        
        requirements = self.assignments[ass]

        for req in requirements:
            if req.package_name not in self.frontiers:
                self.frontiers.insert(0, req.package_name)

        del self.assignments[ass]

    def add_conflict(self, conflict):
        self.conflicts.append(conflict)

    def has_frontiers(self):
        return len(self.frontiers) > 0

    def pop_frontier(self):
        return self.frontiers.pop(0)

    def add_frontier(self, package_name):
        self.frontiers.append(package_name)

    

def solve_dependencies(book):
    while book.has_frontiers():

        package_name = book.pop_frontier()
        logger.debug(f"Looking at package {package_name}:")


        dependency_constraints = book.get_dependency_constraints(package_name)
        logger.debug(f"\tDependency constraints are:")
        for constraint in dependency_constraints:
            logger.debug(f"\t\t{constraint.source} -> {constraint.package_name} {constraint.version_set}")



        if len(dependency_constraints) == 0:
            logger.debug(f"\t\tNo dependents! Removing package!")
            if book.has_assignment(package_name):
                book.remove_assignment(package_name)
            continue



        non_dependency_constraints = book.get_non_dependency_constraints(package_name)
        logger.debug(f"\tOther constraints are:")
        for constraint in non_dependency_constraints:
            logger.debug(f"\t\t{constraint.source} -> {constraint.package_name} {constraint.version_set}")

        
        all_versions = book.get_available_versions(package_name)
        logger.debug(f"\tAvailable versions are: {all_versions}")


        allowed_versions = book.get_allowed_versions(package_name)
        logger.debug(f"\tAllowed versions are: {allowed_versions}")
        


def _solve_dependencies_for(package_name, book):
    _debug_print_package(package_name, book)

    requirements = book.get_requirements_on(package_name)

    all_versions = book.get_available_versions(package_name)

    intersection = verpy.intersection(*[req.version_set for req in requirements])
    allowed_versions = intersection.filter_allowed(all_versions)
    
    if len(allowed_versions) == 0:
        pass

    if book.has_assignment(package_name):
        assignment = book.get_assignment_for(package_name)
        logger.debug(f"\tFound existing assignment: {assignment}")
        
        if assignment.version not in allowed_versions:
            logger.debug(f"\t\tThe existing assignment is not ok! Removing!")
            
            # _resolve_conflict(package_name, [assignment.version], ass_reqs, book)
            
            # book.remove_assignment(package_name)
        elif assignment.version != allowed_versions[0]:
            logger.debug(f"\t\tThe existing assignment is ok but not highest! Removing!")
            book.remove_assignment(package_name)
        else:
            logger.debug(f"\t\tThe existing assignment is ok!")
            return

    logger.debug(f"\tAssigning version {allowed_versions[0]} to {package_name}")
    book.add_assignment(package_name, allowed_versions[0])


def _debug_print_package(package_name, book):
    logger.debug(f"Looking at package {package_name}:")

    ass_reqs = book.get_all_requirements_for_package(package_name)
    logger.debug(f"\tRequirements are:")
    for assignment, requirement in ass_reqs:
        logger.debug(f"\t\t{assignment} -> {requirement}")

    all_versions = book.get_available_versions(package_name)
    logger.debug(f"\tAvailable versions are: {all_versions}")

    intersection = verpy.intersection(*[req.version_set for ass, req in ass_reqs])
    allowed_versions = intersection.filter_allowed(all_versions)
    logger.debug(f"\tAllowed versions are: {allowed_versions}")


class DependencySolver:

    def __init__(self, repo) -> None:
        self._root_dependencies = []
        self.repo = repo

    def add_dependency(self, dependency : verpy.Requirement):
        self._root_dependencies.append(dependency)

    def get_all_dependencies_recursive(self):
        book = Book(self.repo)
        book.add_assignment("root", verpy.version("1.0"), self._root_dependencies)

        for req in self._root_dependencies:
            _solve_dependencies_for(req.package_name, book)

        return book.get_assignments()

    def get_all_dependencies(self):
        book = Book(self.repo)
        book.add_assignment("root", verpy.version("1.0"), list(self._root_dependencies))
       
    
        while book.has_frontiers():
            package_name = book.pop_frontier()
            logger.debug(f"Looking at package {package_name}:")

            ass_reqs = book.get_all_requirements_for_package(package_name)
            logger.debug(f"\tRequirements are:")
            for assignment, requirement in ass_reqs:
                logger.debug(f"\t\t{assignment} -> {requirement}")

            if len(ass_reqs) == 0:
                logger.debug(f"\t\tNo requirements! Removing package!")
                if book.has_assignment(package_name):
                    book.remove_assignment(package_name)
                continue

            all_versions = self.repo.get_versions(package_name)
            logger.debug(f"\tAvailable versions are: {all_versions}")

            # intersection = verpy.intersection(*[req.version_set for ass, req in ass_reqs])
            allowed_versions = book.get_allowed_versions(package_name)
            logger.debug(f"\tAllowed versions are: {allowed_versions}")


            if len(allowed_versions) == 0:
                logger.debug(f"\tNo allowed versions! Running conflict resolution")
                reqs = book.get_requirements_on(package_name)
                logger.debug(reqs)
                exit(0)

            if book.has_assignment(package_name):
                assignment = book.get_assignment_for(package_name)
                logger.debug(f"\tFound existing assignment: {assignment}")
                
                if assignment.version not in allowed_versions:
                    logger.debug(f"\t\tThe existing assignment is not ok! Running conflict resolution!")
                    
                    incompatibilities = self._find_incompatibilities([assignment.version], ass_reqs)

                    for incompat in incompatibilities:
                        incompat.assignments.add(assignment)
                        book.add_conflict(Conflict(incompat, assignment))
                    
                    book.remove_assignment(package_name)
                    book.add_frontier(package_name)
                    continue
                elif assignment.version != allowed_versions[0]:
                    logger.debug(f"\t\tThe existing assignment is ok but not highest! Removing!")
                    book.remove_assignment(package_name)
                else:
                    logger.debug(f"\t\tThe existing assignment is ok!")
                    continue

            logger.debug(f"\tAssigning version {allowed_versions[0]} to {package_name}")
            book.add_assignment(package_name, allowed_versions[0])

        return book.get_assignments()

    def _find_incompatibilities(self, all_versions, ass_reqs):
        # Find the requirements that are conflicting with the assignment
        # by going through all possible requirement combinations
        all_combinations = list(itertools.chain(*[itertools.combinations(ass_reqs, i) for i in range(1, len(ass_reqs)+1)]))
        logger.debug(all_combinations)

        found_incompatibilities = []

        for combination in all_combinations:
            intersection = verpy.intersection(*[req.version_set for ass, req in combination])
            if len(intersection.filter_allowed(all_versions)) == 0:
                assignments = [ass for ass, req in combination]
                found_incompatibilities.append(Incompatibility(assignments))
        
        # Only save the minimal incompatibilities
        to_remove = []
        for incompat_1 in found_incompatibilities:
            for incompat_2 in found_incompatibilities:
                if incompat_1 is not incompat_2:
                    if incompat_1.is_subset_of(incompat_2):
                        to_remove.append(incompat_2)

        for incompat in to_remove:
            found_incompatibilities.remove(incompat)
        
        logger.debug("Found the following incompatibilities")
        logger.debug(f"\t{found_incompatibilities}")
        
        return found_incompatibilities



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
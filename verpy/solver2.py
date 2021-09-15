from . import version as verpy
import itertools
import typing
import logging

logger = logging.getLogger("solver")

class Assignment:

    def __init__(self, package_name, version) -> None:
        self.package_name = package_name
        self.version = version

    def __str__(self) -> str:
        return f"{self.package_name} {self.version}"

    def __repr__(self) -> str:
        return str(self)
    
    def __hash__(self):
        return hash(("Assignment", self.package_name, self.version))

    def __eq__(self, o: object) -> bool:
        return hash(self) == hash(o)


class RootAssignment(Assignment):

    def __init__(self) -> None:
        super().__init__("__root__", "0")
    

class Constraint:
    
    def is_violated_by(self, assignments):
        raise NotImplementedError()

    def get_target_package_names(self):
        raise NotImplementedError()


class DependencyConstraint(Constraint):
    
    def __init__(self, assignment, requirement):
        self.assignment = assignment
        self.requirement = requirement

    def is_violated_by(self, assignments):
        for assignment in assignments:
            if assignment.package_name == self.requirement.package_name:
                if assignment.version not in self.requirement.version_set:
                    return True
        
        return False

    def get_assignments(self):
        return set([self.assignment])

    def get_target_package_names(self):
        return [self.requirement.package_name]

    def is_constraint_on_package(self, package_name):
        return package_name == self.requirement.package_name

    def __str__(self) -> str:
        return f"{self.assignment} -> {self.requirement}"

    def __repr__(self) -> str:
        return str(self)

    def __hash__(self):
        return hash(("DependencyConstraint", self.assignment, self.requirement))

    def __eq__(self, o: object) -> bool:
        return hash(self) == hash(o)


class IncompatibilityConstraint(Constraint):
    
    def __init__(self, assignments, trace_to=None):
        self.assignments = set(assignments)
        self.trace_to = trace_to

    def is_violated_by(self, assignments):
        return self.assignments.issubset(assignments)

    def get_assignments(self):
        return set(self.assignments)

    def get_target_package_names(self):
        return [assignment.package_name for assignment in self.assignments]

    def is_constraint_on_package(self, package_name):
        for assignment in self.assignments:
            if package_name == assignment.package_name:
                return True

        return False

    def issubset(self, other):
        return self.assignments.issubset(other.assignments)

    def __str__(self) -> str:
        return "Not(" + " & ".join([str(a) for a in self.assignments]) + ")"

    def __repr__(self) -> str:
        return str(self)

    def __hash__(self):
        return hash(("IncompatibilityConstraint", *sorted(self.assignments, key=lambda a: hash(a))))

    def __eq__(self, o: object) -> bool:
        return hash(self) == hash(o)


class Book:

    def __init__(self, package_repository) -> None:
        self.repo = package_repository
        self.assignments = []
        self.constraints = []
        self.frontiers = []


    #
    # Assignments
    #

    def get_assignment_for_package(self, package_name):
        
        for assignment in self.assignments:
            if assignment.package_name == package_name:
                return assignment
        
        return None

    def has_assignment_for_package(self, package_name):
        return self.get_assignment_for_package(package_name) is not None

    def add_root_assignment(self, dependencies):
        assert len(self.assignments) == 0

        assignment = RootAssignment()

        self.assignments.append(assignment)

        for requirement in dependencies:
            self.add_constraint(DependencyConstraint(assignment, requirement))

    def add_assignment(self, assignment):
        
        assert not self.has_assignment_for_package(assignment.package_name)

        dependencies = self.repo.get_dependencies(assignment.package_name, assignment.version)
        
        self.assignments.append(assignment)

        for requirement in dependencies:
            self.add_constraint(DependencyConstraint(assignment, requirement))

    def remove_assignment(self, package_name):

        assert self.has_assignment_for_package(package_name)

        assignment = self.get_assignment_for_package(package_name)
        
        self.assignments.remove(assignment)

        for constraint in list(self.constraints):
            if isinstance(constraint, DependencyConstraint) and constraint.assignment == assignment:
                self.remove_constraint(constraint)

    def get_assignments(self):
        return list(self.assignments)

    

    #
    # Constraints
    #

    def add_constraint(self, constraint):
        assert constraint not in self.constraints

        self.constraints.append(constraint)

        for package_name in constraint.get_target_package_names():
            if package_name != "__root__" and package_name not in self.frontiers:
                self.add_frontier(package_name)

    def remove_constraint(self, constraint):
        assert constraint in self.constraints

        self.constraints.remove(constraint)

        for package_name in constraint.get_target_package_names():
            if package_name != "__root__" and package_name not in self.frontiers:
                self.add_frontier(package_name)

    def get_constraints(self):
        return list(self.constraints)

    def get_constraints_for_package(self, package_name):
        constraints_for_package = []

        for constraint in self.constraints:
            if constraint.is_constraint_on_package(package_name):
                constraints_for_package.append(constraint)
        
        return constraints_for_package

    def get_dependency_constraints_for_package(self, package_name):
        constraints_for_package = []

        for constraint in self.constraints:
            if isinstance(constraint, DependencyConstraint) and constraint.is_constraint_on_package(package_name):
                constraints_for_package.append(constraint)
        
        return constraints_for_package

    def get_dependants(self, package_name):
        assignments = []
        for constraint in self.constraints:
            if isinstance(constraint, DependencyConstraint) and constraint.is_constraint_on_package(package_name):
                assignments.append(constraint.assignment)
        
        return assignments

    def has_dependants(self, package_name):
        for constraint in self.constraints:
            if isinstance(constraint, DependencyConstraint) and constraint.is_constraint_on_package(package_name):
                return True
        
        return False

    def violates_any_constraints(self, assignments):
        for constraint in self.constraints:
            if constraint.is_violated_by(assignments):
                return True
        
        return False

    def find_earliest_offending_assignment(self):
        
        for i in range(1, len(self.assignments)+1):
            if self.violates_any_constraints(self.assignments[:i]):
                return self.assignments[i-1]
        
        return None

    #
    # Frontiers
    #

    def has_frontiers(self):
        return len(self.frontiers) > 0

    def pop_frontier(self):
        return self.frontiers.pop(0)

    def add_frontier(self, package_name):
        # logger.debug(f"{package_name} added to frontiers")
        self.frontiers.append(package_name)


    #
    # Package versions
    #

    def get_available_versions(self, package_name):
        return self.repo.get_versions(package_name)

    def get_allowed_versions(self, package_name):

        all_versions = self.get_available_versions(package_name)

        if self.has_assignment_for_package(package_name):
            assignments = list(self.assignments)
            assignments.remove(self.get_assignment_for_package(package_name))
            allowed_versions = _filter_allowed_version(assignments, self.get_constraints_for_package(package_name), package_name, all_versions)
        else:
            allowed_versions = _filter_allowed_version(list(self.assignments), self.get_constraints_for_package(package_name), package_name, all_versions)


        return allowed_versions


def solve_dependencies(root_dependencies, package_repository):
    book = Book(package_repository)
    
    book.add_root_assignment(root_dependencies)

    while book.has_frontiers():
        package_name = book.pop_frontier()
        logger.debug(f"Looking at package {package_name}:")

        constraints = book.get_constraints_for_package(package_name)
        logger.debug(f"\tRelevant constraints are:")
        for constraint in constraints:
            logger.debug(f"\t\t{constraint}")
        
        if not book.has_dependants(package_name):
            logger.debug(f"\tPackage has no dependants. Removing!")
            if book.has_assignment_for_package(package_name):
                book.remove_assignment(package_name)

            continue

        allowed_versions = book.get_allowed_versions(package_name)
        logger.debug(f"\tAllowed versions are: {allowed_versions}")


        if len(allowed_versions) == 0:
            logger.debug(f"\tNo allowed versions! Running conflict resolution")
            constraints = book.get_dependency_constraints_for_package(package_name)
            
            # incompatibilities = _find_incompatibilities(
            #     book.get_assignments(), 
            #     book.get_constraints_for_package(package_name), 
            #     package_name, 
            #     book.get_available_versions(package_name)
            # )

            assignments = book.get_dependants(package_name)


            if len(assignments) == 1 and isinstance(assignments[0], RootAssignment):
                raise Exception("Version solving failed.")

            book.add_constraint(IncompatibilityConstraint(assignments))
 
            # logger.debug(assignments)
            if isinstance(assignments[-1], RootAssignment):
                # logger.debug(f"Removing assignment {assignments[-2]}")
                book.remove_assignment(assignments[-2].package_name)
            else:
                # logger.debug(f"Removing assignment {assignments[-1]}")
                book.remove_assignment(assignments[-1].package_name)
            
            continue

        if book.has_assignment_for_package(package_name):
            assignment = book.get_assignment_for_package(package_name)
            logger.debug(f"\tFound existing assignment: {assignment}")

            if assignment.version not in allowed_versions:
                logger.debug(f"\t\tThe existing assignment is not ok! Running conflict resolution!")
                
                incompatibilities = _find_incompatibilities(
                    book.get_assignments(), 
                    book.get_dependency_constraints_for_package(package_name), 
                    package_name, 
                    [assignment.version]
                )

                for incompatibility in incompatibilities:
                    incompatibility.assignments.add(assignment)

                    book.add_constraint(incompatibility)
                
                book.remove_assignment(package_name)
                continue
            elif assignment.version != allowed_versions[0]:
                logger.debug(f"\t\tThe existing assignment is ok but not highest! Removing!")
                book.remove_assignment(package_name)
            else:
                logger.debug(f"\t\tThe existing assignment is ok!")
                continue
    
        logger.debug(f"\tAssigning version {allowed_versions[0]} to {package_name}")
        book.add_assignment(Assignment(package_name, allowed_versions[0]))

    return list(filter(lambda x: not isinstance(x, RootAssignment), book.get_assignments()))

    

def _find_incompatibilities(assignments, constraints, package_name, all_versions):
    # Find the requirements that are conflicting with the assignment
    # by going through all possible requirement combinations
    all_combinations = list(itertools.chain(*[itertools.combinations(constraints, i) for i in range(1, len(constraints)+1)]))

    incompatibilities = []

    for constraint_combination in all_combinations:
        allowed_versions = _filter_allowed_version(assignments, constraint_combination, package_name, all_versions)
        if len(allowed_versions) == 0:
            assignments = []
            for constraint in constraint_combination:
                assignments.extend(constraint.get_assignments())
            
            incompatibility = IncompatibilityConstraint(assignments, constraint_combination)
            if not _contains_subset(incompatibilities, incompatibility):
                incompatibilities.append(incompatibility)
    

    logger.debug("Found the following incompatibilities")
    logger.debug(f"\t{incompatibilities}")

    return incompatibilities

def _filter_allowed_version(assignments, constraints, package_name, all_versions):
    def allowed_version_filter(version):
        _assignments = assignments + [Assignment(package_name, version)]

        for constraint in constraints:
            if constraint.is_violated_by(_assignments):
                return False
        
        return True


    allowed_versions = list(filter(allowed_version_filter, all_versions))

    return allowed_versions

def _contains_subset(incompatibilities, incompatibility):
    for item in incompatibilities:
        if item.issubset(incompatibility):
            return True
    
    return False



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

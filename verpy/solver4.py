from . import version as verpy
import itertools
import typing
import logging

logger = logging.getLogger("solver")

class SolverError(Exception):
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


class Transaction:

    def __init__(self) -> None:
        self.operations = []

    def merge(self, other):
        self.operations += other.operations

    def apply_all(self, assignments, constraints):
        for operation in self.operations:
            operation.apply(assignments, constraints)

    def add(self, operation):
        self.operations.append(operation)

class Operation:

    def apply(self, assignments, constraints):
        raise NotImplementedError()


class AddAssignment(Operation):

    def __init__(self, assignment) -> None:
        self.assignment = assignment

    def apply(self, assignments, constraints):
        assignments.append(self.assignment)


class RemoveAssignment(Operation):

    def __init__(self, assignment) -> None:
        self.assignment = assignment

    def apply(self, assignments, constraints):
        assignments.remove(self.assignment)


class AddConstraint(Operation):

    def __init__(self, constraint) -> None:
        self.constraint = constraint

    def apply(self, assignments, constraints):
        constraints.append(self.constraint)
    

class RemoveConstraint(Operation):

    def __init__(self, constraint) -> None:
        self.constraint = constraint

    def apply(self, assignments, constraints):
        constraints.remove(self.constraint)


class Book:

    def __init__(self, package_repository) -> None:
        self.repo = package_repository

        self.transactions = [Transaction()]

    @property
    def assignments(self):
        all_assignments = []
        all_constraints = []

        for transaction in self.transactions:
            transaction.apply_all(all_assignments, all_constraints)
        
        return all_assignments

    @property
    def constraints(self):
        all_assignments = []
        all_constraints = []

        for transaction in self.transactions:
            transaction.apply_all(all_assignments, all_constraints)
        
        return all_constraints


    def begin_transaction(self):
        self.transactions.append(Transaction())

    def commit_transaction(self):
        assert len(self.transactions) > 1

        transaction = self.transactions.pop()
        self.transactions[-1].merge(transaction)

    def rollback(self):
        assert len(self.transactions) > 1

        self.transactions.pop()

    #
    # Assignments
    #
    def add_assignment(self, assignment):
        assert not self.has_assignment(assignment.package_name)
        self.transactions[-1].add(AddAssignment(assignment))

    def remove_assignment(self, assignment):
        assert assignment in self.assignments
        self.transactions[-1].add(RemoveAssignment(assignment))

        for constraint in self.constraints:
            if isinstance(constraint, DependencyConstraint) and constraint.assignment == assignment:
                self.remove_constraint(constraint)

        

    def get_assignment(self, package_name):
        for assignment in self.assignments:
            if assignment.package_name == package_name:
                return assignment
        
        return None

    def has_assignment(self, package_name):
        return self.get_assignment(package_name) is not None


    #
    # Constraints
    #

    def add_constraint(self, constraint):
        assert constraint not in self.constraints
        self.transactions[-1].add(AddConstraint(constraint))

    def remove_constraint(self, constraint):
        assert constraint in self.constraints
        self.transactions[-1].add(RemoveConstraint(constraint))
    
        if isinstance(constraint, DependencyConstraint):
            assignment = self.get_assignment(constraint.requirement.package_name)
            if assignment is not None and len(self.get_dependants(assignment.package_name)) == 0:
                self.remove_assignment(assignment)

    def get_constraints_for_package(self, package_name):
        constraints_for_package = []

        for constraint in self.constraints:
            if constraint.is_constraint_on_package(package_name):
                constraints_for_package.append(constraint)
        
        return constraints_for_package

    def get_dependants(self, package_name):
        assignments = []
        for constraint in self.constraints:
            if isinstance(constraint, DependencyConstraint) and constraint.is_constraint_on_package(package_name):
                assignments.append(constraint.assignment)
        
        return assignments

    #
    # Package versions
    #

    def get_available_versions(self, package_name):
        return self.repo.get_versions(package_name)

    def get_allowed_versions(self, package_name):

        all_versions = self.get_available_versions(package_name)

        allowed_versions = _filter_allowed_version(self.assignments, self.get_constraints_for_package(package_name), package_name, all_versions)

        return allowed_versions


    def get_dependencies(self, package_name, package_version):
        return self.repo.get_dependencies(package_name, package_version)


def _filter_allowed_version(assignments, constraints, package_name, all_versions):
    assignments = list(filter(lambda x: x.package_name != package_name, assignments))

    def allowed_version_filter(version):
        _assignments = assignments + [Assignment(package_name, version)]

        for constraint in constraints:
            if constraint.is_violated_by(_assignments):
                return False
        
        return True

    return list(filter(allowed_version_filter, all_versions))




def solve_dependencies(root_dependencies, package_repository):
    book = Book(package_repository)

    root_assignment = RootAssignment()
    book.add_assignment(root_assignment)
    for requirement in root_dependencies:
        book.add_constraint(DependencyConstraint(root_assignment, requirement))
        solve_dependencies_recursive(book, requirement.package_name)


    result = list(filter(lambda a: a is not root_assignment and len(book.get_constraints_for_package(a.package_name)) > 0, book.assignments))

    return result

def solve_dependencies_recursive(book, package_name):
    logger.debug(f"Looking at package {package_name}:")

    constraints = book.get_constraints_for_package(package_name)

    logger.debug(f"\tRelevant constraints are:")
    for constraint in constraints:
        logger.debug(f"\t\t{constraint}")


    allowed_versions = book.get_allowed_versions(package_name)
    logger.debug(f"\tAllowed versions are: {allowed_versions}")

    if len(allowed_versions) == 0:
        raise NoAllowedVersionsError()


    curr_assignment = book.get_assignment(package_name)
    if curr_assignment is not None:
        logger.debug(f"\tFound existing assignment: {curr_assignment}")

        if curr_assignment.version in allowed_versions:
            logger.debug(f"\t\tThe existing assignment is ok!")
            return

        logger.debug(f"\t\tThe existing assignment is not ok!")
        
    
    for version in allowed_versions:
        
        try:
            book.begin_transaction()
            if curr_assignment is not None:
                book.remove_assignment(curr_assignment)
            
            assignment = Assignment(package_name, version)
            logger.debug(f"\tAssigning version {version} to {package_name}")

            book.add_assignment(assignment)
            
            dependencies = book.get_dependencies(package_name, version)
            
            for requirement in dependencies:
                book.add_constraint(DependencyConstraint(assignment, requirement))
                solve_dependencies_recursive(book, requirement.package_name)

            book.commit_transaction()

            return
        except SolverError:
            book.rollback()
    
    logger.debug(f"\tNone of the allowed versions succeded. Failing!")

    raise AllAssignmentsFailed()



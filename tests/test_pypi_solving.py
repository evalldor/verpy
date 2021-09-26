from verpy import solver
from verpy import pypi

def test_pypi_solving_1():
    repo = pypi.PypiRepository()

    result = solver.solve_dependencies(
        root_dependencies=[
            repo.parse_requirement("bar >=1.0"),
            repo.parse_requirement("foo >=1.0 & <2.0")
        ],
        package_repository=repo
    )
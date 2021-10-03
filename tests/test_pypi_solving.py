import logging

from verpy import solver
from verpy import pypi

logging.basicConfig(level="DEBUG")

def test_pypi_solving_1():
    repo = pypi.PypiRepository()

    result = solver.solve_dependencies(
        root_dependencies=[
            repo.parse_requirement("oslo.utils==1.4.0"),
        ],
        package_repository=repo
    )
    
    print(result)
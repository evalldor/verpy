import verpy.version as vp
import verpy.solver2 as solver

import logging
import pytest

logging.basicConfig(level="DEBUG")

def test_solver_1():

    repo = solver.DictRepository({
        "foo": {
            "1.0": [
                "bar >=1.0 & <2.0"
            ]
        },
        "bar": {
            "1.0": [
                "baz 1.0"
            ],
            "2.0": [
                "taz 2.0"
            ]
        },
        "baz": {
            "1.0": []
        },
        "taz": {
            "2.0": []
        }
    })


    
    result = solver.solve_dependencies(
        root_dependencies=[
            vp.requirement("bar >=1.0"),
            vp.requirement("foo >=1.0 & <2.0")
        ],
        package_repository=repo
    )

    assert len(result) == 4
    assert solver.Assignment("__root__", "0") in result
    assert solver.Assignment("foo", vp.version("1.0")) in result
    assert solver.Assignment("bar", vp.version("1.0")) in result
    assert solver.Assignment("baz", vp.version("1.0")) in result

def test_solver_2():

    repo = solver.DictRepository({
        "foo": {
            "1.0": [
                "bar 1.0"
            ]
        },
        "bar": {
            "1.0": [
                "baz 1.0"
            ],
            "2.0": [
                "foo 1.0"
            ]
        },
        "baz": {
            "1.0": []
        }
    })

    result = solver.solve_dependencies(
        root_dependencies=[
            vp.requirement("bar >=1.0")
        ],
        package_repository=repo
    )

    assert len(result) == 3
    assert solver.Assignment("__root__", "0") in result
    assert solver.Assignment("bar", vp.version("1.0")) in result
    assert solver.Assignment("baz", vp.version("1.0")) in result

    # print(result)

def test_solver_3():

    repo = solver.DictRepository({
        "foo": {
            "1.0": [
                "taz >=1.0"
            ],
            "2.0": [
                "taz >=1.0"
            ]
        },
        "bar": {
            "1.0": [
                "baz 1.0"
            ],
            "2.0": [
                "foo 1.0"
            ]
        },
        "taz": {
            "1.0": [
                "bar 1.0"
            ],
            "2.0": [
                "bar 1.0"
            ]
        },
        "baz": {
            "1.0": []
        }
    })

    result = solver.solve_dependencies(
        root_dependencies=[
            vp.requirement("bar >=1.0")
        ],
        package_repository=repo
    )

    assert len(result) == 3
    assert solver.Assignment("__root__", "0") in result
    assert solver.Assignment("bar", vp.version("1.0")) in result
    assert solver.Assignment("baz", vp.version("1.0")) in result
    

def test_solver_4():

    repo = solver.DictRepository({
        "foo": {
            "1.0": [
                "taz >=1.0"
            ]
        },
        "bar": {
            "1.0": [
                "baz 1.0"
            ],
            "2.0": [
                "foo 1.0"
            ]
        },
        "taz": {
            "1.0": [
                "bar 2.0"
            ],
            "2.0": [
                "bar 1.0"
            ]
        },
        "baz": {
            "1.0": []
        }
    })

    result = solver.solve_dependencies(
        root_dependencies=[
            vp.requirement("bar >=1.0")
        ],
        package_repository=repo
    )

    assert len(result) == 4
    assert solver.Assignment("__root__", "0") in result
    assert solver.Assignment("bar", vp.version("2.0")) in result
    assert solver.Assignment("foo", vp.version("1.0")) in result
    assert solver.Assignment("taz", vp.version("1.0")) in result


def test_solver_5():

    with pytest.raises(Exception):
        repo = solver.DictRepository({
            "foo": {
                "1.0": [
                    "bar 1.0"
                ]
            },
            "bar": {
                "2.0": [
                    "foo 1.0"
                ]
            },
            "baz": {
                "1.0": []
            }
        })

        result = solver.solve_dependencies(
            root_dependencies=[
                vp.requirement("bar >=1.0")
            ],
            package_repository=repo
        )

        print(result)
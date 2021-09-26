import logging

import pytest
import verpy.solver as solver

from verpy import version

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
            version.parse_requirement("bar >=1.0"),
            version.parse_requirement("foo >=1.0 & <2.0")
        ],
        package_repository=repo
    )

    assert result == {
        "foo": "1.0",
        "bar": "1.0",
        "baz": "1.0",
    }


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
            version.parse_requirement("bar >=1.0")
        ],
        package_repository=repo
    )

    assert result == {
        "bar": "1.0",
        "baz": "1.0",
    }


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
            version.parse_requirement("bar >=1.0")
        ],
        package_repository=repo
    )

    assert result == {
        "bar": "1.0",
        "baz": "1.0",
    }


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
            version.parse_requirement("bar >=1.0")
        ],
        package_repository=repo
    )

    assert result == {
        "bar": "2.0",
        "foo": "1.0",
        "taz": "1.0"
    }


def test_solver_5():

    with pytest.raises(solver.SolverError):
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
                version.parse_requirement("bar >=1.0")
            ],
            package_repository=repo
        )
        # pass
        # print(result)


def test_solver_6():

    repo = solver.DictRepository({
        "a": {
            "1.0": [
                "x >=1.0"
            ]
        },
        "b": {
            "1.0": [
                "x < 2.0"
            ]
        },
        "c": {
            "1.0": [
            ],
            "2.0": [
                "a >= 1",
                "b >= 1"
            ]
        },
        "x": {
            "0.0": [],
            "1.0": [
                "y 1.0"
            ],
            "2.0": []
        },
        "y": {
            "1.0": [],
            "2.0": []
        }
    })

    result = solver.solve_dependencies(
        root_dependencies=[
            version.parse_requirement("c >=1.0"),
            version.parse_requirement("y >=2.0")
        ],
        package_repository=repo
    )

    assert result == {
        "y": "2.0",
        "c": "1.0"
    }


def test_solver_7():
    repo = solver.DictRepository({
        "foo": {
            "1.0": [
                "bar 1.0"
            ],
            "2.0": [
                "bar 2.0"
            ],
            "3.0": [
                "bar 3.0"
            ]
        },
        "bar": {
            "1.0": [
                "baz >=1.0"
            ],
            "2.0": [
                "foo 2.0"
            ],
            "2.0": [
                "foo 3.0"
            ]
        },
        "baz": {
            "1.0": []
        }
    })

    result = solver.solve_dependencies(
        root_dependencies=[
            version.parse_requirement("foo >=1.0")
        ],
        package_repository=repo
    )
    
    assert result == {
        "bar": "1.0",
        "foo": "1.0",
        "baz": "1.0"
    }


def test_solver_8():

    repo = solver.DictRepository({
        "foo": {
            "1.0": [
                "taz 1.0"
            ]
        },
        "bar": {
            "1.0": [
                "taz >=1.0"
            ],
            "2.0": [
                "taz 3.0"
            ]
        },
        "baz": {
            "1.0": [
                "taz >=1.0"
            ],
            "2.0": [
                "taz <3.0"
            ]
        },
        "taz": {
            "1.0": [],
            "2.0": [],
            "3.0": []
        }
    })

    result = solver.solve_dependencies(
        root_dependencies=[
            version.parse_requirement("bar >=1.0"),
            version.parse_requirement("foo >=1.0"),
            version.parse_requirement("baz >=1.0")
        ],
        package_repository=repo
    )

    assert result == {
        "bar": "1.0",
        "foo": "1.0",
        "baz": "2.0",
        "taz": "1.0"
    }


def test_solver_9():

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
                "baz 1.0"
            ],
            "3.0": [
                "foo 1.0"
            ]
        },
        "baz": {
            "1.0": []
        }
    })

    result = solver.solve_dependencies(
        root_dependencies=[
            version.parse_requirement("bar >=1.0")
        ],
        package_repository=repo
    )

    assert result == {
        "bar": "2.0",
        "baz": "1.0",
    }

import verpy.version as vp
import verpy.solver4 as solver

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

    assert len(result) == 3
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

    assert len(result) == 2
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

    assert len(result) == 2
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
    print(result)
    assert len(result) == 3
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
            vp.requirement("c >=1.0"),
            vp.requirement("y >=2.0")
        ],
        package_repository=repo
    )

    assert len(result) == 2
    assert solver.Assignment("y", vp.version("2.0")) in result
    assert solver.Assignment("c", vp.version("1.0")) in result


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
            vp.requirement("foo >=1.0")
        ],
        package_repository=repo
    )
    
    assert len(result) == 3
    assert solver.Assignment("bar", vp.version("1.0")) in result
    assert solver.Assignment("foo", vp.version("1.0")) in result
    assert solver.Assignment("baz", vp.version("1.0")) in result


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
            vp.requirement("bar >=1.0"),
            vp.requirement("foo >=1.0"),
            vp.requirement("baz >=1.0")
        ],
        package_repository=repo
    )

    # assert len(result) == 2
    # assert solver.Assignment("bar", vp.version("1.0")) in result
    # assert solver.Assignment("baz", vp.version("1.0")) in result

    print(result)

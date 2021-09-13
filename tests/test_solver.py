import verpy
import verpy.version as vp
import verpy.solver as sol

import logging

logging.basicConfig(level="DEBUG")

def test_solver_1():

    repo = sol.DictRepository({
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

    solver = sol.DependencySolver(repo)

    solver.add_dependency(vp.requirement("bar >=1.0"))
    solver.add_dependency(vp.requirement("foo >=1.0 & <2.0"))

    
    result = solver.get_all_dependencies()

    assert len(result) == 4
    assert sol.Assignment("root", vp.version("1.0")) in result
    assert sol.Assignment("foo", vp.version("1.0")) in result
    assert sol.Assignment("bar", vp.version("1.0")) in result
    assert sol.Assignment("baz", vp.version("1.0")) in result

def test_solver_2():

    repo = sol.DictRepository({
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

    solver = sol.DependencySolver(repo)

    solver.add_dependency(vp.requirement("bar >=1.0"))

    print()
    result = solver.get_all_dependencies()

    # assert len(result) == 4
    # assert sol.Assignment("root", vp.version("1.0")) in result
    # assert sol.Assignment("foo", vp.version("1.0")) in result
    # assert sol.Assignment("bar", vp.version("1.0")) in result
    # assert sol.Assignment("baz", vp.version("1.0")) in result

    print(result)
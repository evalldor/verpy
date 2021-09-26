from verpy import version

def test_versions():

    v1 = version.parse_version("01..00.0-alpha.beta.010a-SNAPSHOT")
    v2 = version.parse_version("01.00.0-alpha.01.0b-SNAPSHOT")
    v3 = version.parse_version("1.0-SNAPSHOT")
    
    assert v2 > v1
    assert v3 > v2
    assert version.parse_version("2.0-alpha-1") < version.parse_version("2.0-alpha-2") < version.parse_version("2.0-beta-1")
    assert version.parse_version("v2.1.0-M1") < version.parse_version("Ver2.1.0")    
    assert version.parse_version("1.0-SNAPSHOT") == version.parse_version("1-SNAPSHOT")
    assert hash(version.parse_version("1.0-SNAPSHOT")) == hash(version.parse_version("1-SNAPSHOT"))

    
    rng = version.parse_maven_version_set("(1.0-SNAPSHOT,], 2.0-alpha-1, (2.0-alpha1, 2.0-alpha-2)")
    print(rng)


def test_version_sets():

    vset = version.parse_version_set(">=1.0")
    assert vset.contains(version.parse_version("1.0"))
    assert not vset.contains(version.parse_version("0.9"))
    
    vset = vset.intersection(version.parse_version_set("<2.0"))
    assert vset.contains(version.parse_version("1.0"))
    assert vset.contains(version.parse_version("1.9"))
    assert not vset.contains(version.parse_version("0.9"))
    assert not vset.contains(version.parse_version("2.0"))

    vset = vset.union(version.parse_version_set("3.0"))
    assert vset.contains(version.parse_version("1.0"))
    assert vset.contains(version.parse_version("1.9"))
    assert not vset.contains(version.parse_version("0.9"))
    assert not vset.contains(version.parse_version("2.0"))
    assert vset.contains(version.parse_version("3.0"))
    assert not vset.contains(version.parse_version("2.9"))
    assert not vset.contains(version.parse_version("3.1"))

    vset = version.parse_version_set("<=3.0").difference(version.parse_version_set(">2.0"))
    assert vset.contains(version.parse_version("2.0"))
    assert vset.contains(version.parse_version("1.0"))
    assert not vset.contains(version.parse_version("2.1"))
    assert not version.parse_version("3.0") in vset


    vset = version.parse_version_set("<= 1.0 | >3.0")
    assert version.parse_version("1.0") in vset
    assert version.parse_version("2.0") not in vset

    vset = version.parse_version_set("<= 1.0 or >3.0")
    assert version.parse_version("1.0") in vset
    assert version.parse_version("2.0") not in vset

    vset = version.parse_version_set("(>=1.0, <3.0)")
    assert version.parse_version("2.0") in vset

    vset = version.parse_version_set(">=1.0 and <3.0")
    assert version.parse_version("2.0") in vset

    vset = version.parse_version_set("!(<= 1.0 or >3.0)")
    assert version.parse_version("1.0") not in vset
    assert version.parse_version("2.0") in vset
    

def test_requirement():

    req = version.parse_requirement("verpy >= 1.0 & < 2.0")
    print(req)


def test_python_version():
    import packaging
    import packaging.requirements
    import os

    v = packaging.version.Version("2.2")    

    r = packaging.requirements.Requirement("asd[abc] >= 2.1")    

    assert v in r.specifier

    print(r.marker.evaluate({"extra": "hello"}))
    
    requirements = [version.Requirement(r.name, r.specifier)]
    for e in r.extras:
        requirements.append(version.Requirement(f"{r.name}$__extra__${e}", r.specifier))

    print(requirements)
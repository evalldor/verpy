import verpy as vp

def test_versions():

    v1 = vp.version("01..00.0-alpha.beta.010a-SNAPSHOT")
    v2 = vp.version("01.00.0-alpha.01.0b-SNAPSHOT")
    v3 = vp.version("1.0-SNAPSHOT")
    
    assert v2 > v1
    assert v3 > v2
    assert vp.version("2.0-alpha-1") < vp.version("2.0-alpha-2") < vp.version("2.0-beta-1")
    assert vp.version("v2.1.0-M1") < vp.version("Ver2.1.0")    
    assert vp.version("1.0-SNAPSHOT") == vp.version("1-SNAPSHOT")
    assert hash(vp.version("1.0-SNAPSHOT")) == hash(vp.version("1-SNAPSHOT"))
    
    rng = vp.maven_set("(1.0-SNAPSHOT,], 2.0-alpha-1, (2.0-alpha1, 2.0-alpha-2)")
    # print(rng)

def test_version_sets():
    vset = vp.set(">=1.0")
    assert vset.contains("1.0")
    assert not vset.contains("0.9")
    
    vset = vset.intersection("<2.0")
    assert vset.contains("1.0")
    assert vset.contains("1.9")
    assert not vset.contains("0.9")
    assert not vset.contains("2.0")

    vset = vset.union("3.0")
    assert vset.contains("1.0")
    assert vset.contains("1.9")
    assert not vset.contains("0.9")
    assert not vset.contains("2.0")
    assert vset.contains("3.0")
    assert not vset.contains("2.9")
    assert not vset.contains("3.1")

    vset = vp.set("<=3.0").difference(">2.0")
    assert vset.contains("2.0")
    assert vset.contains("1.0")
    assert not vset.contains("2.1")
    assert not "3.0" in vset


    vset = vp.set(">= 1.0 | 3.0")
    print(vset)

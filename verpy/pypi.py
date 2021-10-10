import typing

import requests

from . import version
from .solver import PackageRepository

import packaging
import packaging.requirements
import packaging.version


class PypiRepository(PackageRepository):

    def __init__(self) -> None:
        super().__init__()

    def get_dependencies(self, package_name, package_version, flags=[]) -> typing.List[version.Requirement]:
        
        info = requests.get(f"https://pypi.org/pypi/{package_name}/{package_version}/json").json()
        
        requires_dist = info["info"]["requires_dist"]
        
        requirements = []

        if requires_dist is not None:
            for string in requires_dist:
                req = packaging.requirements.Requirement(string)
                if req.marker is None or any(req.marker.evaluate(environment={"extra": e}) for e in flags):
                    requirements.append(version.Requirement(req.name, req.specifier, req.extras))

        return requirements
            
    
    def get_versions(self, package_name):
        info = requests.get(f"https://pypi.org/pypi/{package_name}/json").json()

        return [packaging.version.parse(v) for v in info["releases"].keys()]


    def parse_requirement(self, string, extra=""):
        req = packaging.requirements.Requirement(string)
        
        return version.Requirement(req.name, req.specifier, req.extras)

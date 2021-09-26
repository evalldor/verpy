import typing

import requests

from . import version
from .solver import PackageRepository


import packaging
import packaging.requirements

class PypiRepository(PackageRepository):

    def __init__(self) -> None:
        super().__init__()

    def get_dependencies(self, package_name, package_version) -> typing.List[version.Requirement]:
        
        if "$__extra__$" in package_name:
            name, extra = package_name.split("$__extra__$")

            info = requests.get(f"https://pypi.org/pypi/{name}/{package_version}/json").json()

            requirements = info["requires_dist"]

            normal_requirements = []
            for requirement in requirements:
                normal_requirements.extend(self.parse_requirement(requirement))

            extra_requirements = []
            for requirement in requirements:
                parsed_reqs = self.parse_requirement(requirement, extra)
                for req in parsed_reqs:
                    if req not in normal_requirements:
                        extra_requirements.extend(req)

            return 
        else:
            info = requests.get(f"https://pypi.org/pypi/{package_name}/{package_version}/json").json()

            requirements = info["requires_dist"]

            normal_requirements = []
            for requirement in requirements:
                normal_requirements.extend(self.parse_requirement(requirement))
            
    
    def get_versions(self, package_name):
        if "$__extra__$" in package_name:
            name, extra = package_name.split("$__extra__$")
            
        info = requests.get(f"https://pypi.org/pypi/{package_name}/json").json()

        return [packaging.version.Version(v) for v in info["releases"].keys()]


    def parse_requirement(self, string, extra=""):
        req = packaging.requirements.Requirement(string)
        
        if req.marker is not None:
            if not req.marker.evaluate({"extras": extra}):
                return []

        requirements = [version.Requirement(req.name, req.specifier)]
        
        for e in req.extras:
            requirements.append(version.Requirement(f"{req.name}$__extra__${e}", req.specifier))
        
        return requirements

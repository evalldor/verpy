import typing
from . import version as vp
from .solver import PackageRepository
import requests

class PypiRepository(PackageRepository):

    def __init__(self) -> None:
        super().__init__()

    def get_dependencies(self, package_name, package_version) -> typing.List[vp.Requirement]:
        info = requests.get(f"https://pypi.org/pypi/{package_name}/{package_version}/json").json()

        requirements = info["requires_dist"]
        
    
    def get_versions(self, package_name) -> typing.List[vp.Version]:
        info = requests.get(f"https://pypi.org/pypi/{package_name}/json").json()

        return [vp.version(v) for v in info["releases"].keys()]
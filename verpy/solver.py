import typing
from . import version as verpy


class DependencySolver:

    def __init__(self) -> None:
        self._root_dependencies = []
        self._repositories = []

    def add_repository(self, repo):
        self._repositories.append(repo)

    def add_dependency(self, dependency : verpy.Requirement):
        self._root_dependencies.append(dependency)

    def _get_versions(self, package_name):
        pass

    def _get_dependencies(self, package_name, package_version) -> typing.List[verpy.Requirement]:
        pass

    


class Repository:

    def get_versions(self, package_name):
        pass

    def get_dependencies(self, package_name, package_version) -> typing.List[verpy.Requirement]:
        pass
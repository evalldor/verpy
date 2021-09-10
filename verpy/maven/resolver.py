import pathlib
import re
import dataclasses
import typing
import requests

from . import verpy as vp
from .metadata import MavenArtifactMetadata, MavenSnapshotMetadata
from .pom import Pom

@dataclasses.dataclass(frozen=True)
class MavenArtifact:
    group_id: str = None
    artifact_id: str = None
    version: str = None
    classifier: str = None
    extension: str = "jar"

    @staticmethod
    def from_string(artifact_string):
        """
        group_id:artifact_id[:version[:classifier[@extension]
        """

        parts = artifact_string.split("@")

        assert len(parts) <= 2, "Invalid artifact string"

        if len(parts) == 2:
            extension = parts[1]
        else:
            extension = "jar"

        parts = parts[0].split(":")

        assert len(parts) <= 4 and len(parts) >= 2, "Invalid artifact string"

        group_id = parts[0]
        artifact_id = parts[1]

        if len(parts) > 2:
            version = parts[2]
        else:
            version = None

        if len(parts) > 3:
            classifier = parts[3]
        else: 
            classifier = None
        
        return MavenArtifact(
            group_id=group_id, 
            artifact_id=artifact_id, 
            version=version, 
            classifier=classifier, 
            extension=extension
        )
    
    def is_version_snapshot(self):
        return self.version is not None and self.version.upper().endswith("-SNAPSHOT")

    def is_version_latest(self):
        return self.version is None or self.version.upper() == "LATEST"

    @property
    def basepath(self):
        return "/".join([*self.group_id.split("."), self.artifact_id, self.version])
    
    @property
    def basename(self):
        if self.classifier:
            return f"{self.artifact_id}-{self.version}-{self.classifier}"
        
        return f"{self.artifact_id}-{self.version}"
        

@dataclasses.dataclass(frozen=True)
class Requirement:
    group_id: str = None
    artifact_id: str = None
    version: str = None
    classifier: str = None
    extension: str = "jar" #Aka 'type'

    @staticmethod
    def from_string(requirement_string):
        """
        group_id:artifact_id[:version[:classifier[@extension]
        """

        parts = requirement_string.split("@")

        assert len(parts) <= 2, "Invalid artifact string"

        if len(parts) == 2:
            extension = parts[1]
        else:
            extension = "jar"

        parts = parts[0].split(":")

        assert 2 <= len(parts) <= 4, "Invalid artifact string"

        group_id = parts[0]
        artifact_id = parts[1]

        if len(parts) > 2:
            version = VersionSet.from_string(parts[2])
        else:
            version = None #Allow any version

        if len(parts) > 3:
            classifier = parts[3]
        else: 
            classifier = None
        
        return Requirement(
            group_id=group_id, 
            artifact_id=artifact_id, 
            version=version,
            classifier=classifier, 
            extension=extension
        )

    @property
    def basepath(self):
        return "/".join([*self.group_id.split("."), self.artifact_id])


class MavenResolver:

    def __init__(self):
        self.repositories = []
        self.resolved_artifacts = {}

    def add_repo(self, repo):
        self.repositories.append(repo)

    def resolve(self, dependencies: typing.List[typing.Union[str, dict]], transitive=True):
        artifacts_to_resolve = []

        for dep in dependencies:
            if isinstance(dep, str):
                artifacts_to_resolve.append(MavenArtifact.from_string(dep))
            else:
                artifacts_to_resolve.append(MavenArtifact(**dep))

        resolved_dependencies = []

        for dep in artifacts_to_resolve:
            is_resolved = False
            for repo in self.repositories:
                resolved = repo.find(dep)

                if resolved is not None:
                    is_resolved = True
                    resolved_dependencies.append(resolved)
                    break
            
            if not is_resolved:
                raise Exception(f"Unresolvable dependency '{dep}'.")
        
        return resolved_dependencies

class FsRepository:

    def __init__(self, basedir):
        self._basedir = pathlib.Path(basedir)
    
    def find(self, artifact):
        if artifact.is_version_latest():
            raise Exception("Internal Error. Need specific version to find.")
        
        artifact_path = self._basedir.joinpath(*artifact.group_id.split("."), artifact.artifact_id)

        if not artifact_path.exists():
            return None
        
        version = None
        
        if artifact.is_version_snapshot():
            pass
        else:
            version = artifact.version

        path_with_version = artifact_path.joinpath(str(version))

        return path_with_version
    
    def get_available_versions_for_artifact(self, artifact):
        artifact_path = self._basedir.joinpath(*artifact.group_id.split("."), artifact.artifact_id)

        versions = []

        if artifact_path.exists():
            for directory in artifact_path.iterdir():
                versions.append(Version.from_string(directory.name))

        return versions


class RemoteRepository:
    
    def __init__(self, baseurl):
        self.baseurl = Url(baseurl)

    def find(self, artifact):
        artifact_url = self.baseurl.join(artifact.basepath, f"{artifact.basename}.{artifact.extension}")
        
        response = requests.get(str(artifact_url))

        if response.status_code != requests.codes.ok:
            return None

        

    def get_dependencies_for_artifact(self, artifact):
        pass

    def get_pom(self, artifact):

        pom_url = self.baseurl.join(artifact.basepath, f"{artifact.basename}.pom")

        response = requests.get(str(pom_url))

        if response.status_code != requests.codes.ok:
            return None

        return Pom(response.text)

    def get_available_versions_for_requirement(self, requirement):

        metadata_url = self.baseurl.join(requirement.basepath, "maven-metadata.xml")
        response = requests.get(str(metadata_url))

        if response.status_code != requests.codes.ok:
            return []
        
        metadata = MavenArtifactMetadata.from_xml(response.text)

        return [Version(v) for v in metadata.all_versions]


import urllib.parse
class Url:

    def __init__(self, url: typing.Union[str, urllib.parse.ParseResult]):
        if isinstance(url, str):
            self._url = urllib.parse.urlparse(url)
        elif isinstance(url, urllib.parse.ParseResult):
            self._url = url

    def join(self, *parts: str):
        new_parts = self._url._asdict()
        new_parts["path"] = "/".join([self._url.path, *parts]).replace("//", "/")

        return Url(urllib.parse.ParseResult(**new_parts))

    def __str__(self):
        return urllib.parse.urlunparse(self._url)

    def __repr__(self):
        return str(self)

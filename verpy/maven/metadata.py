import dataclasses
import typing

from bs4 import BeautifulSoup

@dataclasses.dataclass
class MavenArtifactMetadata:
    group_id: str = None
    artifact_id: str = None

    latest_version: str = None
    release_version: str = None

    last_updated: str = None

    all_versions: typing.List[str] = None

    @staticmethod
    def from_xml(xml_string):
        soup = BeautifulSoup(xml_string, 'xml')
        
        group_id = soup.metadata.groupId
        artifact_id = soup.metadata.artifactId

        latest_version = soup.metadata.versioning.latest
        release_version = soup.metadata.versioning.release

        last_updated = soup.metadata.versioning.lastUpdated

        versions = soup.metadata.versioning.versions.find_all("version", recursive=False)
        
        all_versions = [v.string for v in versions]
        
        return MavenArtifactMetadata(
            group_id=group_id,
            artifact_id=artifact_id,
            latest_version=latest_version,
            release_version=release_version,
            last_updated=last_updated,
            all_versions=all_versions
        )

@dataclasses.dataclass
class MavenSnapshotMetadata:
    group_id: str = None
    artifact_id: str = None
    version: str = None
    
    latest_snapshot_timestamp: str = None
    latest_snapshot_buildnumber: str = None

    last_updated: str = None

    # all_snapshot_versions: typing.List[str] = None

    @staticmethod
    def from_xml(xml_string):
        pass


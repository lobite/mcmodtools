import logging, aiohttp
from modtools.api import ModrinthAPI
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class VersionStatus:
    LATEST_RELEASE = 10 # latest mod version is release, and is for the target game version
    LATEST_NONRELEASE_W_RELEASE = 11 # newer alpha/beta is available for the target game verison as well as a (likely) more stable release
    LATEST_NONRELEASE_ONLY = 12 # latest mod version is alpha/beta for the target game version
    LEGACY_RELEASE = 20 # latest mod version is release, but isn't for the target game version
    LEGACY_NONRELEASE_W_RELEASE = 21 # newer alpha/beta is available as well as a (likely) more stable release, but not for the target game version
    LEGACY_NONRELEASE_ONLY = 22 # latest mod version is alpha/beta, but isn't for the target game version
    UNAVAILABLE = 30 # no versions available for your mod loader
    MANUAL = 40 # version id manually set

class Mod():
    def __init__(self, api: ModrinthAPI, query: str, game_version: str, is_slug: bool, version_id:str = None):
        # allow passing an API instance for connection pooling. Otherwise, instantiate internally
        self.API = api
        self.query = query
        self.slug: str = query if is_slug else None
        self.project_id: str = query if not is_slug else None
        self.game_version: str = game_version
        self.manual_version_id: str = version_id
        self.version_status: int
        self.version = None
        self.version_alt = None
        self._using_alt_ver = False
        self.poupulated = False
        self.installed = False
        self.path: Path = None
    
    async def populate_data(self):
        if self.slug == None:
            try:
                self.slug = await self.API.get_slug_from_id(self.query)
            except aiohttp.ClientResponseError as e:
                logger.warning(f'{self.query} is invalid. Error: {e}')
                raise e
        self.data = await self.API.get_async(f'project/{self.slug}')
        if self.project_id == None: self.project_id = self.data['id']
        if not self.manual_version_id:
            # automatically search matching version
            await self._get_versions()
        else:
            # use manually specified version id (for retrieving dependencies)
            self.version_status = VersionStatus.MANUAL
            self.version = await self.API.get_async(f'version/{self.manual_version_id}')
        self._selected = False if self.version_status in (VersionStatus.LATEST_NONRELEASE_W_RELEASE, VersionStatus.LEGACY_NONRELEASE_W_RELEASE) else True
        if self._selected: self.dependencies = await self._fetch_dependencies()
        self.populated = True
        return self

    @property
    def using_alt_ver(self):
        return self._using_alt_ver
    
    @using_alt_ver.setter
    async def use_alt(self):
        if not self.versions['status'] in (VersionStatus.LATEST_NONRELEASE_W_RELEASE, VersionStatus.LEGACY_NONRELEASE_W_RELEASE):
            logger.info(f'use_alt() was called on {self.slug}, but this mod has no alt versions. Ignoring.')
            pass
        else:
            self._using_alt_ver = True
            self._selected = True
            await self._fetch_dependencies()
    
    @property
    def selected(self):
        return self.selected
    
    async def _get_versions(self):
        # fetch_versions sorts versions by release date, so next() should return the latest matching version
        all_versions = await self.API.fetch_versions(self.slug)

        # find compatible versions
        target_versions = list(filter(
            lambda v: ("fabric" in v['loaders']) and (self.game_version in v['game_versions']),
            all_versions
        ))

        if target_versions:
            # the mod has versions supporting the game version
            # latest release
            release_version_latest = next(
                    (v
                    for v in target_versions
                    if v['version_type'] == "release"), None
                )
            # latest alpha/beta
            nonrelease_version_latest = next(
                    (v
                    for v in all_versions
                    if v['version_type'] != "release"), None
                )
            if not nonrelease_version_latest and not release_version_latest:
                logger.error(f"Encountered a problem finding mod versions for {self.slug}.")
                raise Exception("Program should have found mod versions for the game version, but it is empty.")
            elif not nonrelease_version_latest:
                # mod only has "release" version for game version
                status = VersionStatus.LATEST_RELEASE
                version = release_version_latest
                version_alt = None
            elif not release_version_latest:
                # mod only has alpha/beta version for game version
                status = VersionStatus.LATEST_NONRELEASE_ONLY
                version = nonrelease_version_latest
                version_alt = None
            else:
                release_timestamp = datetime.fromisoformat(release_version_latest['date_published'])
                nonrelease_timestamp = datetime.fromisoformat(nonrelease_version_latest['date_published'])
                if release_timestamp > nonrelease_timestamp:
                    # the latest version is "release"
                    status = VersionStatus.LATEST_RELEASE
                    version = release_version_latest
                    version_alt = None
                else:
                    # the alpha/beta bleeding edge version exists, but a release also exists.
                    # user must pick.
                    self.version_status = VersionStatus.LATEST_NONRELEASE_W_RELEASE
                    self.version = release_version_latest
                    self.version_alt = nonrelease_version_latest
        else:
            # the mod does not support the current version of the game explicitly. it may still support it implicitly
            logger.warning(f'No versions of {self.slug} found for {self.game_version}')
            # latest "release" version
            target_version_release = next(
                (v
                for v in all_versions
                if ("fabric" in v['loaders']) and (v['version_type'] == "release")), None
            )
            # latest alpha/beta version
            target_version_nonrelease = next(
                (v
                for v in all_versions
                if ("fabric" in v['loaders']) and (v['version_type'] != "release")), None
            )
            
            if not target_version_release and not target_version_nonrelease:
                # the mod has zero versions available for fabric
                logger.warning(f"Could not a find compatible version of {self.slug} for fabric. Skipping")
                
                status = VersionStatus.UNAVAILABLE
                version = None,
                version_alt = None
                
            elif not target_version_release and target_version_nonrelease:
                # there are only alpha/beta versions available on previous game versions
                status = VersionStatus.LEGACY_NONRELEASE_ONLY
                version = target_version_nonrelease
                version_alt = None
            elif target_version_release and not target_version_nonrelease:
                # there are only release versions available on previous game versions
                status = VersionStatus.LEGACY_RELEASE
                version = target_version_release
                version_alt = None
            else:
                release_timestamp = datetime.fromisoformat(target_version_release['date_published'])
                nonrelease_timestamp = datetime.fromisoformat(target_version_nonrelease['date_published'])
                if release_timestamp > nonrelease_timestamp:
                    # the latest release version available is newer than the latest alpha/beta available
                    status = VersionStatus.LEGACY_RELEASE
                    version = target_version_release
                    version_alt = None
                else:
                    # the latest compatible version is in alpha/beta while an older release is also available
                    # user must choose which to use
                    status = VersionStatus.LEGACY_NONRELEASE_W_RELEASE
                    version = target_version_release
                    version_alt = target_version_nonrelease
        self.version_status = status
        self.version = version
        self.version_alt = version_alt
    
    async def _fetch_dependencies(self):
        version = self.version_alt if self._using_alt_ver else self.version
        try:
            return await self.API.check_dependencies(version['id'])
        except TypeError as e:
            print(e)
            print(version)
            logger.fatal(f'{self.slug} has no version data, code {self.version_status}')
    
    def get_dependencies(self) -> list['Mod']:
        res = []
        for d in self.dependencies:
            res.append(Mod(self.API, d['project_id'], self.game_version, is_slug=False, version_id = d['version_id']))
        return res

    async def install(self, install_dir: Path):
        version = self.version_alt if self._using_alt_ver else self.version
        if not version: logger.fatal(f'{self.slug} has no version data, code {self.version_status}')
        try:
            file_to_get = next(f for f in version['files'] if f['primary'] == True)
        except StopIteration:
            logger.error(f"{self.slug} {version['name']} has no primary file, proceeding with first file in list")
            file_to_get = version['files'][0]
        mod_location = await self.API.download(file_to_get, install_dir)
        self.path = mod_location
        self.installed = True
        return mod_location
        

    def locate_file(self):
        if self.path.is_file():
            return self.path
        elif self.installed == False:
            return None
        else:
            self.installed = False
            logger.error(f"Could not locate .jar file for {self.slug}")
    
    def update(self):
        pass

    def create_dict(self) -> dict:
        if self._selected:
            return {
                "name": self.slug,
                "project_id": self.project_id,
                "version": self.version_alt['name'] if self._using_alt_ver else self.version['name'],
                "version_id": self.version_alt['id'] if self._using_alt_ver else self.version['id'],
                "file": self.path.name if self.installed else "NOT_INSTALLED",
                "dependencies": self.dependencies if self.dependencies else []
            }
        pass
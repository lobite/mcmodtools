import requests, time, logging, aiohttp, asyncio
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)
SESSION = aiohttp.ClientSession()

class ModrinthAPI:
    def __init__(self):
        self.connection = requests.Session()
        self.root = "https://api.modrinth.com/v2/"
        self.reqcount = 0
        self.maxcalls = 200
        self.accesstime = int(time.time() * 1000)
        self.minute = 60 * 1000

    def ratelimit(self):
        self.reqcount += 1
        if self.reqcount == 1:
            self.accesstime = int(time.time() * 1000)
            return
        else: elapsed = int(time.time() * 1000) - self.accesstime
        if elapsed < self.minute and self.reqcount == self.maxcalls:
            logger.info("Rate limited... pausing")
            self.reqcount = 0
            time.sleep(60 - elapsed)
            logger.info("resumed")
            self.accesstime = int(time.time() * 1000)
        elif elapsed >= self.minute:
            self.reqcount = 0

    def get(self, url, params=''):
        try:
            self.ratelimit()
            r = self.connection.get(self.root + url, params=params)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as err:
            raise err
    
    async def get_async(self, url: str, params=''):
        self.ratelimit()
        async with SESSION.get(url, params) as response:
            return await response.json()

    def download(self, version_id, install_dir: Path):
        try:
            self.ratelimit()
            v = self.connection.get(self.root + f'version/{version_id}')
            v.raise_for_status()
            ver = v.json()
            try:
                file_to_get = next(f for f in ver['files'] if f['primary'] == True)
            except StopIteration:
                logger.error(f"{ver['name']} has no primary file, proceeding with first file in list")
                file_to_get = ver['files'][0]
            file_path = Path(install_dir) / file_to_get['filename']
            if not file_path.is_file():
                logger.info(f'Downloading {file_to_get['filename']}...')
                self.ratelimit()
                c = self.connection.get(file_to_get['url'])
                with file_path.open('xb') as f:
                    f.write(c.content)
                logger.info(f'Finished downloading {file_to_get['filename']}...')
                return file_path
            else: logger.info(f'{file_to_get['filename']} already exists.')
        except requests.exceptions.RequestException as err:
            raise err

    def get_slug_from_id(self, mod_id) -> str:
        self.ratelimit()
        res = self.connection.get(f'https://modrinth.com/mod/{mod_id}', allow_redirects=False)
        res.raise_for_status()
        return res.headers['location'].removeprefix('/mod/')

    def fetch_versions(self, query):
        # query is either the mod slug or the mod project id
        url = f'project/{query}/version'
        all_versions = self.get(url)
        all_versions.sort(key=lambda v: datetime.fromisoformat(v['date_published']))
        return all_versions

    def check_dependencies(self, version_id) -> list[str]:
        url = f'version/{version_id}'
        res = self.get(url)
        dep = []
        for d in res['dependencies']:
            if d['dependency_type'] == 'required':
                dep.append({
                    "slug": self.get_slug_from_id(d['project_id']),
                    "version_id": d['version_id']
                })
        return dep

MODRINTH_API = ModrinthAPI()
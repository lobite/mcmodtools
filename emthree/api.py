import time, logging, aiohttp
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class ModrinthAPI():
    def __init__(self, session):
        self.session = session
        self.root = "https://api.modrinth.com/v2/"
        self.reqcount = 0
        self.reqcount_total = 0
        self.maxcalls = 300
        self.last_req = time.time()
        self.init_req = time.time()

    def ratelimit(self):
        self.reqcount += 1
        self.reqcount_total += 1
        if self.reqcount_total == 1: self.init_req = time.time()
        if self.reqcount == 1:
            self.last_req = time.time()
            return
        else: elapsed = time.time() - self.last_req
        if elapsed < 60.0 and self.reqcount == self.maxcalls:
            logger.info("Rate limited... pausing")
            self.reqcount = 0
            time.sleep(60.0 - elapsed)
            logger.info("resumed")
            self.last_req = time.time()
        elif elapsed >= 60.0:
            self.reqcount = 0

    async def get_async(self, url: str):
        self.ratelimit()
        async with self.session.get(self.root + url) as response:
            return await response.json()

    async def download(self, file_to_get, install_dir: Path):
        try:
            file_path = Path(install_dir) / file_to_get['filename']
            if not file_path.is_file():
                self.ratelimit()
                async with self.session.get(file_to_get['url']) as c:
                    with open(file_path, 'xb') as f:
                        while True:
                            chunk = await c.content.read(1024)
                            if not chunk: break
                            f.write(chunk)
                
                return file_path
            else: logger.info(f'{file_to_get['filename']} already exists.')
        except aiohttp.ClientConnectionError as err:
            raise err

    async def get_slug_from_id(self, mod_id) -> str:
        self.ratelimit()
        res = await self.session.get(f'https://modrinth.com/mod/{mod_id}', allow_redirects=False)
        res.raise_for_status()
        return res.headers['location'].removeprefix('/mod/')

    async def fetch_versions(self, query):
        # query is either the mod slug or the mod project id
        url = f'project/{query}/version'
        all_versions = await self.get_async(url)
        all_versions.sort(key=lambda v: datetime.fromisoformat(v['date_published']))
        return all_versions

    async def check_dependencies(self, version_id) -> list[str]:
        url = f'version/{version_id}'
        self.ratelimit()
        res = await self.get_async(url)
        dep = []
        for d in res['dependencies']:
            if d['dependency_type'] == 'required':
                dep.append({
                    "project_id": d['project_id'],
                    "version_id": d['version_id']
                })
        return dep

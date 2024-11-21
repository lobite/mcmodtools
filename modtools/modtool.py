import requests
import time

class ModrinthAPI:
    def __init__(self):
        self.API = "https://api.modrinth.com/v2/"
        self.reqcount = 0
        self.maxcalls = 300
        self.accesstime = time.time_ns()
        self.minute = 60 * 10 ** 9

    def ratelimit(self):
        self.reqcount += 1
        if self.reqcount == 1:
            self.accesstime = time.time_ns()
        elapsed = time.time_ns() - self.accesstime
        if elapsed < self.minute and self.reqcount >= self.maxcalls:
            print("Rate limited... pausing")
            self.reqcount = 0
            time.sleep(self.minute - elapsed)
            print("resumed")
        elif elapsed >= self.minute:
            self.reqcount = 0

    def get(self, url, params=''):
        try:
            self.ratelimit()
            r = requests.get(self.API + url, params=params)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as err:
            raise err

    def download(self, mod, path):
        try:
            self.ratelimit()
            v = requests.get(self.API + f'version/{mod["version_id"]}')
            v.raise_for_status()
            ver = v.json()
            print("AAAAAAAAAAA" + str(ver))
            self.ratelimit()
            c = requests.get(ver['files'][0]['url'])
            open(path + ver['files'][0]['filename'], "xb").write(c.content)
            return ver['files'][0]['filename']
        except requests.exceptions.RequestException as err:
            raise err

    def fetch_versions(self, mod_id, game_version=None):
        filter = {
            "game_version": [game_version],
            "loaders": ["fabric"]
        }
        url = f'project/{mod_id}/version'
        return self.get(url, filter)
    
    def check_dependencies(self, version_id):
        url = f'version/{version_id}'
        res = self.get(url)
        dep = []
        for d in res['dependencies']:
            if d['dependency_type'] == 'required':
                dep.append(d['project_id'])
        return dep
    
    def get_mod(self, id_or_slug, game_version=None):
        res = self.get(f'project/{id_or_slug}')
        id = res['id']
        latest = self.fetch_versions(id, game_version)[0]
        dependencies = self.check_dependencies(latest['id'])
        return {
            "name": latest['name'],
            "project_id": id,
            "version_id": latest['id'],
            "date": latest['date_published'],
            "dependencies": dependencies
        }


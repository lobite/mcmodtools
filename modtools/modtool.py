import requests
import time

class ModrinthAPI:
    def __init__(self, config):
        self.API = "https://api.modrinth.com/v2/"
        self.reqcount = 0
        self.maxcalls = 300
        self.accesstime = time.time_ns()
        self.minute = 60 * 10 ** 9
        self.config = config

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

    def download(self, url, path):
        try:
            self.ratelimit()
            c = requests.get(url)
            c.raise_for_status()
            open(path, "xb").write(c.content)
        except requests.exceptions.RequestException as err:
            raise err

    def fetch_versions(self, mod_id, game_version=None):
        if game_version == None:
            game_version = self.config['game_version']
        filter = {
            "game_version": [game_version],
            "loaders": ["fabric"]
        }
        url = f'project/{mod_id}/version'
        return self.get(url, filter)
    
    def check_dependencies(self, mod_id):
        url = f'project/{mod_id}/dependencies'
        res = self.get(url)
        return [dep['id'] for dep in res['projects']]
    
    def get_mod(self, name, game_version=None):
        if game_version == None:
            game_version = self.config['game_version']
        res = self.get(f'project/{name}')
        id = res['id']
        latest = self.fetch_versions(id, game_version)[0]
        dependencies = self.check_dependencies(id)
        return {
            "name": name,
            "project_id": id,
            "version_id": latest['id'],
            "date": latest['date_published'],
            "dependencies": dependencies
        }


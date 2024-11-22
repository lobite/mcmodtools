import requests
import time
from pathlib import Path
from modtools.prompt import prompt
from modtools.exceptions import UserCancel

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
            file_to_get = next(f for f in ver['files'] if f['primary'] == True)
            mod_file = Path(path + file_to_get['filename'])
            if not mod_file.is_file():
                self.ratelimit()
                c = requests.get(file_to_get['url'])
                with mod_file.open('xb') as f:
                    f.write(c.content)
                print(f'downloaded {file_to_get["filename"]}')
                mod['filename'] = file_to_get["filename"]
                return mod
            else:
                print(f'file for {mod["name"]} already exists, skipping')
        except requests.exceptions.RequestException as err:
            raise err

    def get_slug_from_id(self, mod_id):
        res = requests.get(f'https://modrinth.com/mod/{mod_id}', allow_redirects=False)
        res.raise_for_status()
        return res.headers['location'].removeprefix('/mod/')

    def fetch_versions(self, query, game_version, slug):
        url = f'project/{query}/version'
        all_versions = self.get(url)
        mod_name = query if slug else self.get_slug_from_id(query)
        target_version = next(
            (v
            for v in all_versions
            if ("fabric" in v['loaders']) and (game_version in v['game_versions'])), None
        )
        if target_version == None:
            print(f'[WARN]: No versions of {mod_name} found for {game_version}')
            target_version = next(
                (v
                for v in all_versions
                if "fabric" in v['loaders']), None
            )
            if target_version == None:
                print("[ERROR]: could not find compatible version. skipping")
                return {
                    'status': 1,
                    'version': None,
                    'version_alt': None
                }
            else:
                return {
                    'status': 4,
                    'version': target_version,
                    'version_alt': None
                }
        is_stable = any(
            v
            for v in all_versions
            if (game_version in v['game_versions']) and (v['version_type'] == "release")
        )
        if target_version['version_type'] == "release":
            return {
                'status': 0,
                'version': target_version,
                'version_alt': None
            }
        elif is_stable and target_version['version_type'] != 'release':
            newest_release = next(
                (v
                for v in all_versions
                if "fabric" in v['loaders'] and game_version in v['game_versions'] and v['version_type'] == 'release'), None
            )
            print(f'[WARN]: latest version {target_version["name"]} for {mod_name} is {target_version["version_type"]}, and a release version {newest_release["name"]} is available.')
            return {
                'status': 2,
                'version': target_version,
                'version_alt': newest_release
            }
        elif not is_stable:
            print(f'[WARN]: {mod_name} has no stable release.')
            return {
                'status': 3,
                'version': target_version,
                'version_alt': None
            }

    def check_dependencies(self, version_id):
        url = f'version/{version_id}'
        res = self.get(url)
        dep = []
        for d in res['dependencies']:
            if d['dependency_type'] == 'required':
                dep.append(d['project_id'])
        return dep
    
    def get_mod(self, query, game_version, slug):
        try:
            candidates = self.fetch_versions(query, game_version, slug)
        except Exception as e:
            raise e

        dependencies = []
        dependencies_alt = []
        if candidates['status'] == 1:
            return
        if candidates['version'] != None:
            dependencies = self.check_dependencies(candidates['version']['id'])
        if candidates['version_alt'] != None:
            dependencies_alt = self.check_dependencies(candidates['version_alt']['id'])
        return {
            "name": query if slug else self.get_slug_from_id(query),
            "project_id": query if not slug else candidates['version']['project_id'],
            "versions": candidates,
            "dependencies": {
                "version": dependencies,
                "version_alt": dependencies_alt
            }
        }

    def resolve_conflict(self, mod):
        match mod['versions']['status']:
            case 0:
                return {
                    "name": mod['name'],
                    "version": mod['versions']['version']['name'],
                    "version_type": mod['versions']['version']['version_type'],
                    "project_id": mod['project_id'],
                    "version_id": mod['versions']['version']['id'],
                    "dependencies": mod['dependencies']['version']
                }
            case 1:
                print(f'no compatible version was found for {mod["name"]}, and was skipped')
                return None
            case 2:
                if prompt(f'use release version over latest version for {mod["name"]}?'):
                    return {
                        "name": mod['name'],
                        "version": mod['versions']['version_alt']['name'],
                        "version_type": mod['versions']['version_alt']['version_type'],
                        "project_id": mod['project_id'],
                        "version_id": mod['versions']['version_alt']['id'],
                        "dependencies": mod['dependencies']['version_alt']
                    }
                else:
                    return {
                        "name": mod['name'],
                        "version": mod['versions']['version']['name'],
                        "version_type": mod['versions']['version']['version_type'],
                        "project_id": mod['project_id'],
                        "version_id": mod['versions']['version']['id'],
                        "dependencies": mod['dependencies']['version']
                    }
            case 3:
                if prompt(f'[WARN]: {mod["name"]} has no stable release. continue?'):
                    return {
                        "name": mod['name'],
                        "version": mod['versions']['version']['name'],
                        "version_type": mod['versions']['version']['version_type'],
                        "project_id": mod['project_id'],
                        "version_id": mod['versions']['version']['id'],
                        "dependencies": mod['dependencies']['version']
                    }
                else: return None
            case 4:
                if prompt(f'[WARN]: {mod["name"]} has no release for specified game version. continue?'):
                    return {
                        "name": mod['name'],
                        "version": mod['versions']['version']['name'],
                        "version_type": mod['versions']['version']['version_type'],
                        "project_id": mod['project_id'],
                        "version_id": mod['versions']['version']['id'],
                        "dependencies": mod['dependencies']['version']
                    }
                else: return None
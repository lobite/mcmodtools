import requests
import csv
import json
import argparse
import time
from pathlib import Path
import concurrent.futures

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

with open('config.json', 'r') as config_file:
        config = json.load(config_file)
# TODO: Pass optional arguments to config
modAPI = ModrinthAPI(config)

def parse_args():
    parser = argparse.ArgumentParser(
        prog="modtools",
        description="A CLI tool to automatically download and maintain Minecraft mods from Modrinth",
    )
    parser.add_argument("list_path",
                        help="Path to CSV list containing mods")
    parser.add_argument("-p", "--mod_path",
                        default="./mods",
                        help="Path to download mods to")
    parser.add_argument("-v", "--version",
                        default="1.21.1")
    parser.add_argument("-u", "--update")
    parser.add_argument("-i", "--install")

    return parser.parse_args()

args = parse_args()

def prompt(q):
    while True:
        i = input(f'{q} (Y/n): ')
        if i == 'Y':
            return True
        elif i == 'n':
            return False


def parse_user_list(path):
    prefix_a = "https://modrinth.com/mod/"
    prefix_b = "https://modrinth.com/datapack/"
    column_modrinth_link = 4
    column_server_side = 8
    modlist = []
    with open(path, "r", newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            if row[column_server_side] == "TRUE":
                modName = row[column_modrinth_link].replace(prefix_a, '').replace(prefix_b, '')
                modlist.append(modName)
                modlist = list(filter(None, modlist))
    return modlist

def fetch_user_list(modlist):
    mods = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for mod in modlist:
            futures.append(executor.submit(modAPI.get_mod, name=mod))
            print(f'fetching mod {mod}...')
        for future in concurrent.futures.as_completed(futures):
            res_mod = future.result()
            mods.append(res_mod)
            print(f'fetched mod {res_mod['name']}')
        
    return mods



def main():
    modlist_file = Path('modlist.json')
    if modlist_file.is_file():
        with modlist_file.open('r') as f:
            modlist = json.load(f)
    elif prompt("Modlist not located, fetch mods?"):
        modlist = fetch_user_list(parse_user_list(args.list_path))
        print(modAPI.reqcount)
        # print(getMod(collection[0]), args.version)

if __name__ == "__main__":
    main()
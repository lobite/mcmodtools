import csv
import argparse
import json
from pathlib import Path
import concurrent.futures
from platformdirs import user_config_dir, user_data_dir
from modtool import ModrinthAPI
from exceptions import UserCancel

modAPI = ModrinthAPI()

def load_config(prod=False):
    if prod:
        config_file = Path(user_config_dir + 'config.json')
        if config_file.is_file():
            with config_file.open('r') as f:
                return json.load(f)
        else:
            # create config file
            defaults = {
                "game" : {
                    "game_version": "1.21.1",
                    "mod_path": "./mods/"
                },
                "modtools" : {
                    "list_path": user_data_dir
                }
            }
            with config_file.open('w') as f:
                json.dump(defaults, f, indent=4)
                return defaults
    # dev configs
    else:
        with open('config.json', 'r') as config_file:
            return json.load(config_file)

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
    userlist = []
    with open(path, "r", newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            if row[column_server_side] == "TRUE":
                modName = row[column_modrinth_link].replace(prefix_a, '').replace(prefix_b, '')
                userlist.append(modName)
                userlist = list(filter(None, userlist))
    return userlist

def batch_get_mod(batch):
    batch_mods = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for mod in batch:
            futures.append(executor.submit(modAPI.get_mod, id_or_slug=mod))
        for future in concurrent.futures.as_completed(futures):
            res_mod = future.result()
            batch_mods.append(res_mod)
            print(f'fetched mod {res_mod['name']}')
    return batch_mods

def batch_download(batch, path):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for mod in batch:
            futures.append(executor.submit(modAPI.download, mod=mod, path=path))
        for future in concurrent.futures.as_completed(futures):
            print(f'downloaded {future.result()}')

def create_modlist(userlist, path):
    modlist = batch_get_mod(userlist)
    print(f'loaded {len(modlist)} mods, checking missing dependencies...')
    discovered_dependencies = auto_get_dependencies(modlist)
    if not prompt("add missing dependencies to list?"):
        raise UserCancel('cancelled retrieving missing dependencies')
    modlist += batch_get_mod(discovered_dependencies)
    with open(path, 'w') as f:
        json.dump(modlist, f, indent=4)
    return modlist

def auto_get_dependencies(modlist):
    known_dependencies = set([d for m in modlist for d in m['dependencies']])
    new_dependencies = []
    total_discovered = 0
    while True:
        new_discovered = 0
        for d in known_dependencies:
            if (not any(m['project_id'] == d for m in modlist)) and (not any(nd == d for nd in new_dependencies)):
                new_dependencies.append(d)
                new_discovered += 1
        if new_discovered == 0:
            break
        total_discovered += new_discovered
    print(f'{total_discovered} dependencies detected')
    return filter(None, new_dependencies)
    


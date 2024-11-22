import csv
import argparse
import json
import time
from pathlib import Path
import concurrent.futures
from platformdirs import user_config_dir, user_data_dir
from modtools.modtool import ModrinthAPI
from modtools.exceptions import UserCancel
from modtools.prompt import prompt

modAPI = ModrinthAPI()

def load_config(prod=True):
    if prod:
        config_path = Path(user_config_dir() + '/mcmodtools/')
        if not config_path.is_dir():
            config_path.mkdir()
        config_file = Path(user_config_dir() + '/mcmodtools/' + 'mcmodtools-config.json')
        if config_file.is_file():
            with config_file.open('r') as f:
                return json.load(f)
        else:
            # create config file
            # the / after the directory is SUPER NECESSARY!!!!
            defaults = {
                "game" : {
                    "game_version": "1.21.1",
                    "mod_path": "./mods/"
                },
                "modtools" : {
                    "list_path": user_data_dir() + '/mcmodtools/'
                }
            }
            with config_file.open('w') as f:
                json.dump(defaults, f, indent=4)
                return defaults
    # dev configs
    else:
        with open('test/config.json', 'r') as config_file:
            return json.load(config_file)

def parse_args():
    parser = argparse.ArgumentParser(
        prog="modtools",
        description="A CLI tool to automatically download and maintain Minecraft mods from Modrinth",
    )
    parser.add_argument("-u", "--userlist",
                        help="Path to CSV list containing mods")
    parser.add_argument("-p", "--mod_path",
                        help="Path to download mods to, if NOT specified in config")
    parser.add_argument("-i", "--install")

    return parser.parse_args()


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

def batch_get_mod(batch, game_version, slug):
    batch_mods = []
    # for mod in batch:
    #     batch_mods.append(modAPI.get_mod(mod, game_version))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        # count = 0
        for mod in batch:
            futures.append(executor.submit(modAPI.get_mod, query=mod, game_version = game_version, slug = slug))
            print(f'fetching {mod}...')
            # count += 1
            # if count % 5 == 0:
            #     time.sleep(5)
        for future in concurrent.futures.as_completed(futures):
            res_mod = future.result()
            batch_mods.append(res_mod)
            print(f'fetched mod {res_mod["name"]}')
    return batch_mods

def batch_download(batch, path):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for mod in batch:
            futures.append(executor.submit(modAPI.download, mod=mod, path=path))
        for future in concurrent.futures.as_completed(futures):
            try: mod = future.result()
            except Exception as e: raise e
    return batch

def create_modlist(userlist, path, game_version):
    modlist = batch_get_mod(userlist, game_version, slug=True)
    modlist_resolved = []
    for mod in modlist:
        modlist_resolved.append(modAPI.resolve_conflict(mod))
    modlist_resolved = list(filter(lambda i: i is not None, modlist_resolved))
    print(f'loaded {len(modlist_resolved)} mods from provided list, checking missing dependencies...')
    discovered_dependencies_list = auto_get_dependencies(modlist_resolved)
    discovered_dependencies_list_named = []
    print("retrieveing names...")
    for dd in discovered_dependencies_list:
        discovered_dependencies_list_named.append(modAPI.get_slug_from_id(dd))
        time.sleep(1)
    print(*discovered_dependencies_list_named, sep=', ')
    if not prompt("add missing dependencies to list?"):
        raise UserCancel('cancelled retrieving missing dependencies')
    discovered_dependencies = batch_get_mod(discovered_dependencies_list, game_version, slug=False)
    discovered_dependencies_resolved = []
    for dd in discovered_dependencies:
        discovered_dependencies_resolved.append(modAPI.resolve_conflict(dd))
    discovered_dependencies_resolved = list(filter(lambda i: i is not None, discovered_dependencies_resolved))
    modlist_resolved += discovered_dependencies_resolved
    with open(path, 'w') as f:
        json.dump(modlist_resolved, f, indent=4)
    return modlist_resolved

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
    new_dependencies = list(filter(lambda i: i is not None, new_dependencies))
    print(f'{total_discovered} missing dependencies detected')
    return new_dependencies
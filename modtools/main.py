import json
import concurrent.futures
from pathlib import Path
from modtool import ModrinthAPI
from utils import parse_args, parse_user_list, prompt

with open('config.json', 'r') as config_file:
        config = json.load(config_file)
# TODO: Pass optional arguments to config

modAPI = ModrinthAPI(config)
args = parse_args()

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
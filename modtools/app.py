import json, argparse
from pathlib import Path
from modtools.exceptions import UserCancel
from modtools.utils import parse_args, parse_user_list, prompt, load_config, create_modlist, batch_download
from modtools.modtool import ModrinthAPI


# TODO: Pass optional arguments to config

def init(args, config, modlist_file):
    userlist_exists = False
    setup = False
    if args.userlist != None:
        userlist_exists = Path(args['userlist']).is_file()
        if not userlist_exists:
            print(f'{args['userlist']} does not exist.')
            return
    if (not modlist_file.is_file()) and (not userlist_exists):
        print('neither generated list nor user list were found. exiting')
        return
    if not modlist_file.is_file():
        print('setting up')
        try:
            modlist = create_modlist(parse_user_list(args.userlist), modlist_file, config['game']['game_version'])
            setup = True
        except UserCancel as e:
            print(e)
            return
    if (not setup) and modlist_file.is_file() and (not userlist_exists):
        with modlist_file.open('r') as f:
            modlist = json.load(f)
    elif (not setup) and prompt('generated list already exists. override?'):
        try:
            modlist = create_modlist(parse_user_list(args.userlist), modlist_file, config['game']['game_version'])
        except UserCancel as e:
            print(e)
            return
    else:
        with modlist_file.open('r') as f:
            modlist = json.load(f)

    print(*[m['name'] for m in modlist], sep=', ')
    if prompt(f'{len(modlist)} mods successfully loaded. download?'):
        try:
            modlist = batch_download(modlist, config['game']['mod_path'])
            print(f'modtools successfully downloaded {len(modlist)} mods to {config["game"]["mod_path"]}')
            with open(modlist_file, 'w') as f:
                json.dump(modlist, f, indent=4)
        except Exception as e:
            raise e
        
def add_mod(args, config, modlist_file):
    mod_name = args.mod
    mods_to_add = []
    with open(modlist_file, "r") as f:
        known_mods = json.load(f)
    if any(m["name"] == mod_name for m in known_mods):
        print("this mod already exists")
        return
    api = ModrinthAPI()
    mod = api.get_mod(mod_name, config["game"]["game_version"], True)
    mod = api.resolve_conflict(mod)
    mods_to_add.append(mod)
    for d_id in mod["dependencies"]:
        d_name = api.get_slug_from_id(d_id)
        print(f'checking {d_name}...')
        d = api.get_mod(d_name, config["game"]["game_version"], True)
        d = api.resolve_conflict(d)
        if not (any(m["project_id"] == d_id for m in known_mods) or any(m["project_id"] == d_id for m in mods_to_add)): 
            mods_to_add.append(d)
    print(*list(m["name"] for m in mods_to_add), sep=', ')
    if prompt("add these mods to the list?"):
        with open(modlist_file, "w") as f:
            json.dump(known_mods + mods_to_add, f, indent=4)
        if prompt("download these mods?"):
            batch_download(mods_to_add, config["game"]["mod_path"])

    

def main():
    config = load_config(prod=False)

    # command arguments initiation
    parser = argparse.ArgumentParser(
        prog="modtools",
        description="A CLI tool to automatically download and maintain Minecraft mods from Modrinth",
    )

    subparsers = parser.add_subparsers(required=True)

    parser_add = subparsers.add_parser('add')
    parser_add.set_defaults(func=add_mod)
    parser_add.add_argument('mod', type=str)


    parser_init = subparsers.add_parser('init')
    parser_init.set_defaults(func=init)
    parser_init.add_argument("-u", "--userlist",
                        help="Path to CSV list containing mods")
    parser_init.add_argument("-p", "--mod_path",
                        help="Path to download mods to, if NOT specified in config")
    parser_init.add_argument("-i", "--install")

    


    list_path = Path(config["modtools"]["list_path"])
    if not list_path.is_dir():
        list_path.mkdir()
    list_file = config["modtools"]["list_path"] + 'modlist.json'
    modlist_file = Path(list_file)
    args = parser.parse_args()
    
    args.func(args, config=config, modlist_file=modlist_file)
    

def list_installed(config, args):
    list_file = config["modtools"]["list_path"] + 'modlist.json'
    modlist_file = Path(list_file)
    try:
        with modlist_file.open('r') as f:
            modlist = json.load(f)
    except FileNotFoundError:
        print("modlist.json could not be found.")
        return
    for mod in modlist:
        if 'filename' in mod:
            installed = Path(f"{config['game']['mod_path']}/{mod['filename']}").is_file()
        else: installed = False
        print(f'- {mod['name']}: {mod['filename'] if installed else "NOT INSTALLED"}')
    print("Caution: Emthree only tracks mods listed in modlist.json. It has no knowledge of mods you may have added manually.")

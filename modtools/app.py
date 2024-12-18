import json
from pathlib import Path
from modtools.exceptions import UserCancel
from modtools.utils import parse_args, parse_user_list, prompt, load_config, create_modlist, batch_download


# TODO: Pass optional arguments to config



def main():
    config = load_config(prod=False)
    args = vars(parse_args())
    print(args)
    actions = {
        "userlist": generateList,
        "list": list_installed
    }
    actions[args['subparser_name']](config, args)
    
def generateList(config, args):
    list_path = Path(config["modtools"]["list_path"])
    if not list_path.is_dir():
        list_path.mkdir()
    list_file = config["modtools"]["list_path"] + 'modlist.json'
    modlist_file = Path(list_file)
    userlist_exists = False
    setup = False
    if args['userlist'] != None:
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
            modlist = create_modlist(parse_user_list(args['userlist']), list_file, config['game']['game_version'])
            setup = True
        except UserCancel as e:
            print(e)
            return
    if (not setup) and modlist_file.is_file() and (not userlist_exists):
        with modlist_file.open('r') as f:
            modlist = json.load(f)
    elif (not setup) and prompt('generated list already exists. override?'):
        try:
            modlist = create_modlist(parse_user_list(args['userlist']), list_file, config['game']['game_version'])
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

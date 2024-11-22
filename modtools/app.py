import json
from pathlib import Path
from modtools.exceptions import UserCancel
from modtools.utils import parse_args, parse_user_list, prompt, load_config, create_modlist, batch_download


# TODO: Pass optional arguments to config



def main():
    config = load_config(prod=False)
    args = parse_args()
    list_path = config["modtools"]["list_path"] + 'modlist.json'
    modlist_file = Path(list_path)
    userlist_exists = False
    setup = False
    if args.userlist != None:
        userlist_exists = Path(args.userlist).is_file()
        if not userlist_exists:
            print(f'{args.userlist} does not exist.')
            return
    if (not modlist_file.is_file()) and (not userlist_exists):
        print('neither generated list nor user list were found. exiting')
        return
    if not modlist_file.is_file():
        print('setting up')
        try:
            modlist = create_modlist(parse_user_list(args.userlist), list_path, config['game']['game_version'])
            setup = True
        except UserCancel as e:
            print(e)
            return
    if (not setup) and modlist_file.is_file() and (not userlist_exists):
        with modlist_file.open('r') as f:
            modlist = json.load(f)
    elif (not setup) and prompt('generated list already exists. override?'):
        try:
            modlist = create_modlist(parse_user_list(args.userlist), list_path, config['game']['game_version'])
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

if __name__ == "__main__":
    main()
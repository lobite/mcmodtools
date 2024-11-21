import json
from pathlib import Path
from modtools.exceptions import UserCancel
from modtools.utils import parse_args, parse_user_list, prompt, load_config, create_modlist, batch_download


# TODO: Pass optional arguments to config



def main():
    config = load_config(prod=True)
    args = parse_args()
    list_path = config["modtools"]["list_path"] + 'modlist.json'
    modlist_file = Path(list_path)
    if modlist_file.is_file() and (not prompt("a list of mods generated by this program already exists. overwrite?")):
        with modlist_file.open('r') as f:
            modlist = json.load(f)
    else:
        try:
            modlist = create_modlist(parse_user_list(args.list_path), list_path, config['game']['game_version'])
        except UserCancel as e:
            print(e)
            return
    print(*[m['name'] for m in modlist], sep=', ')
    if prompt(f'{len(modlist)} mods successfully loaded. download?'):
        try:
            batch_download(modlist, config['game']['mod_path'])
            print(f'modtools successfully downloaded {len(modlist)} mods to {config["game"]["mod_path"]}')
        except Exception as e:
            print(e)
            # print(getMod(collection[0]), args.version)

if __name__ == "__main__":
    main()
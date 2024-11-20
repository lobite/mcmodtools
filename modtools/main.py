import json
from pathlib import Path
from modtool import ModrinthAPI
from utils import parse_args, parse_user_list, prompt, load_config, create_modlist


# TODO: Pass optional arguments to config



def main():
    config = load_config(prod=False)
    args = parse_args()
    list_path = config["modtools"]["list_path"] + 'modlist.json'
    modlist_file = Path(list_path)
    if modlist_file.is_file():
        with modlist_file.open('r') as f:
            modlist = json.load(f)
    else:
        prompt("Modlist not located, fetch mods?")
        modlist = create_modlist(parse_user_list(args.list_path), list_path)
        # print(getMod(collection[0]), args.version)

if __name__ == "__main__":
    main()
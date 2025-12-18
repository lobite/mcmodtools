import json, argparse, logging
from pathlib import Path
from modtools.exceptions import UserCancel
from modtools.utils import get_mod, prompt, load_config, batch_download, batch_get_mod, load_userlist
from modtools.mod import Mod

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# TODO: Pass optional arguments to config

def init(args, config: dict, modlist_file: Path):
    # check user supplied list
    ul = None
    if args.userlist and Path(args.userlist).is_file():
        logger.info(f'loading supplied user-made list of mods from: {args.userlist}')
        ul = load_userlist(Path(args.userlist))
    elif args.userlist:
        logger.info(f'{args.userlist} does not exist.')
        return
    
    setup = False
    # check for generated list
    if (ul and not modlist_file.is_file()) or (ul and modlist_file and prompt('generated list already exists. override?')):
        setup = True
        mods_to_load = ul       
    elif not ul and modlist_file.is_file():
        logger.info(f'user-made list not specified, and found generated list.')
        with modlist_file.open('r') as f:
            modlist = json.load(f)
            mods_to_load = [m['name'] for m in modlist]
    else:
        logger.info('Neither user supplied list nor generated list can be found. Exiting')
        return
    game_ver = config['game']['game_version']
    print(*mods_to_load, sep=', ')
    mods = [get_mod(q, game_ver, is_slug=True) for q in mods_to_load]
    mods = list(filter(None, mods))
    slugs = [mod.slug for mod in mods]
    print(*slugs, sep=', ')
    logger.info(f'{len(slugs)} mods successfully loaded. Checking for dependencies...')

    # algorithm for recursively searching dependencies
    dependencies = []
    dependencies_new = []
    # first, add known dependencies that aren't already in the list
    for m in mods:
        to_add = list(filter(lambda d: d['slug'] not in slugs, m.dependencies))
        discovered = [Mod(d['slug'], game_ver, is_slug=True, version_id = d['version_id']) for d in to_add]
        discovered = list(filter(None, discovered))
        dependencies_new += discovered
        slugs += [mod.slug for mod in discovered]

    dependencies += dependencies_new
    
    # recursively search and add dependencies until no new ones are discovered
    last_len = 0
    while len(dependencies) != last_len:
        discovered_new = []
        for m in dependencies_new:
            to_add = list(filter(lambda d: d['slug'] not in slugs, m.dependencies))
            discovered = [Mod(d['slug'], game_ver, is_slug=True, version_id = d['version_id']) for d in to_add]
            discovered = list(filter(None, discovered))
            discovered_new += discovered
            slugs += [mod.slug for mod in discovered]
        dependencies += dependencies_new
        dependencies_new = discovered_new
        last_len = len(dependencies)

    logger.info(f'Found the following dependencies:')
    print(*[d.slug for d in dependencies])

    if prompt('Download all?'):
        if not any(Path(config['game']['mod_path']).iterdir()):
            try:
                batch_download(mods + dependencies, Path(config['game']['mod_path']))
                logger.info(f'Emthree successfully downloaded {len(mods + dependencies)} mods to {config["game"]["mod_path"]}')
                
            except Exception as e:
                raise e
        else:
            logger.warning(f'Directory is not empty. Proceeding without downloading.')
    if prompt('Write result to file?'):
        with open(modlist_file, 'w') as f:
            modlist_dict = [m.create_dict() for m in mods]
            json.dump(modlist_dict, f, indent=4)
    
        
def add_mod(args, config, modlist_file):
    mod_name = args.mod
    with open(modlist_file, "r") as f:
        known_mods = json.load(f)
    if any(m["name"] == mod_name for m in known_mods):
        logger.info("This mod already exists")
        return
    mod = get_mod(mod_name, config["game"]["game_version"], is_slug=True)
    if mod: dependencies: list[Mod] = mod.get_dependencies()

    # recursively search dependencies
    count = len(dependencies)
    while len(dependencies) != count:
        for d in dependencies:
            dependencies += d.get_dependencies()
        count = len(dependencies)
    mods_to_add = [mod] + dependencies
    print(*list(m.slug for m in mods_to_add), sep=', ')
    if prompt("Add these mods to the list?"):
        with open(modlist_file, "w") as f:
            json.dump(known_mods + mods_to_add, f, indent=4)
        if prompt("Download all?"):
            batch_download(mods_to_add, config["game"]["mod_path"])

def list_installed(args, config, modlist_file):
    try:
        with modlist_file.open('r') as f:
            modlist = json.load(f)
    except FileNotFoundError:
        print("modlist.json could not be found.")
        return
    for mod in modlist:
        if 'filename' in mod:
            installed = (Path(config['game']['mod_path']) / mod['filename']).is_file()
        else: installed = False
        print(f'- {mod['name']}: {mod['filename'] if installed else "NOT INSTALLED"}')
    print("Caution: Emthree only tracks mods listed in modlist.json. It has no knowledge of mods you may have added manually.")

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

    parser_list = subparsers.add_parser('list')
    parser_list.set_defaults(func=list_installed)

    list_path = Path(config["modtools"]["list_path"])
    if not list_path.is_dir():
        list_path.mkdir()
    modlist_file = list_path / 'modlist.json'

    args = parser.parse_args()
    
    args.func(args, config=config, modlist_file=modlist_file)
    



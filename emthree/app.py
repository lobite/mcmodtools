import json, argparse, logging, aiohttp, asyncio, time
from pathlib import Path
from emthree.utils import get_mod, prompt, load_config, load_userlist
from emthree.mod import Mod
from emthree.api import ModrinthAPI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# TODO: Pass optional arguments to config

async def init(args, config: dict, modlist_file: Path):
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

    async with aiohttp.ClientSession() as session:
        api_session = ModrinthAPI(session)
        mods_tasks = [get_mod(api_session, q, game_ver, is_slug=True) for q in mods_to_load]
        mods = await asyncio.gather(*mods_tasks)
        mods = list(filter(None, mods))
        ids = [mod.project_id for mod in mods]
        logger.info(f'{len(ids)} mods successfully loaded. Checking for dependencies...')

        # algorithm for recursively searching dependencies
        dependencies = []
        dependencies_new = []
        # first, add known dependencies that aren't already in the list
        for m in mods:
            to_add = list(filter(lambda d: d['project_id'] not in ids, m.dependencies))
            populate_task = [get_mod(api_session, d['project_id'], game_ver, is_slug=False, version_id = d['version_id']) for d in to_add]
            discovered = []
            for res in asyncio.as_completed(populate_task):
                d = await res
                discovered += [d]
                logger.info(f'Found and loaded dependency {d.slug}')
            dependencies_new += discovered
            ids += [mod.project_id for mod in discovered]
        dependencies += dependencies_new
        
        # recursively search and add dependencies until no new ones are discovered
        last_len = 0
        while len(dependencies) != last_len:
            discovered_new = []
            for m in dependencies_new:
                to_add = list(filter(lambda d: d['project_id'] not in ids, m.dependencies))
                populate_task = [get_mod(api_session, d['project_id'], game_ver, is_slug=False, version_id = d['version_id']) for d in to_add]
                discovered = []
                for res in asyncio.as_completed(populate_task):
                    d = await res
                    discovered += [d]
                    logger.info(f'Found and loaded dependency {d.slug}')
                discovered_new += discovered
                ids += [mod.id for mod in discovered]
            dependencies += discovered_new
            dependencies_new = discovered_new
            last_len = len(dependencies)
        logger.info(f'Loaded the following {len(mods)} from list:')
        print(*[m.slug for m in mods], sep=' ')
        logger.info(f'Found the following {last_len} dependencies:')
        print(*[d.slug for d in dependencies], sep=' ')

        if prompt('Download all?'):
            if not any(Path(config['game']['mod_path']).iterdir()):
                try:
                    install_task = [m.install(Path(config['game']['mod_path'])) for m in mods + dependencies]
                    for finished_dl in asyncio.as_completed(install_task):
                        res = await finished_dl
                        logger.info(f'Finished downloading {res}')
                    logger.info(f'Emthree successfully downloaded {len(mods + dependencies)} mods to {config["game"]["mod_path"]}')
                    
                except Exception as e:
                    raise e
            else:
                logger.warning(f'Directory is not empty. Aborted download operation.')
        logger.info(f'Made {api_session.reqcount_total} requests in {round(time.time() - api_session.init_req, 2)} secs\n')
    if prompt('Write result to file?'):
        with open(modlist_file, 'w') as f:
            modlist_dict = [m.create_dict() for m in mods]
            json.dump(modlist_dict, f, indent=4)
    
        
async def add_mod(args, config, modlist_file):
    mod_name = args.mod
    with open(modlist_file, "r") as f:
        known_mods = json.load(f)
    if any(m["name"] == mod_name for m in known_mods):
        logger.info("This mod already exists")
        return
    api_session = ModrinthAPI()
    mod = await get_mod(api_session, mod_name, config["game"]["game_version"], is_slug=True)
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
            try:
                install_task = [m.install(Path(config['game']['mod_path'])) for m in mods_to_add]
                async for finished_dl in asyncio.as_completed(install_task):
                    res = await finished_dl
                    logger.info(f'Finished downloading {res}')
                logger.info(f'Emthree successfully downloaded {len(mods_to_add)} mods to {config["game"]["mod_path"]}')
                
            except Exception as e:
                raise e

async def list_installed(args, config, modlist_file):
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

async def main():
    config = load_config(prod=False)

    # command arguments initiation
    parser = argparse.ArgumentParser(
        prog="emthree",
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

    list_path = Path(config["emthree"]["list_path"])
    if not list_path.is_dir():
        list_path.mkdir()
    modlist_file = list_path / 'modlist.json'

    args = parser.parse_args()

    
    await args.func(args, config=config, modlist_file=modlist_file)
    



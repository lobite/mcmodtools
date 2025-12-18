import argparse, json, time, logging, re
from pathlib import Path
import concurrent.futures
from platformdirs import user_config_dir, user_data_dir
from modtools.modtool import MODRINTH_API
from modtools.exceptions import UserCancel
from modtools.mod import Mod, VersionStatus

logger = logging.getLogger(__name__)

modAPI = MODRINTH_API

def load_config(prod=True):
    if prod:
        config_path = Path(user_config_dir()) / 'mcmodtools'
        if not config_path.is_dir():
            config_path.mkdir()
        config_file = Path(user_config_dir()) / 'mcmodtools' / 'mcmodtools-config.json'
        if config_file.is_file():
            with config_file.open('r') as f:
                return json.load(f)
        else:
            # create config file
            mod_path = input(f'Specify mod folder location: ')
            defaults = {
                "game" : {
                    "game_version": "1.21.1",
                    "mod_path": mod_path
                },
                "modtools" : {
                    "list_path": Path(user_data_dir()) / 'mcmodtools'
                }
            }
            with config_file.open('w') as f:
                json.dump(defaults, f, indent=4)
                return defaults
    # dev configs
    else:
        with open('test/config.json', 'r') as config_file:
            return json.load(config_file)

def prompt(q: str) -> bool:
    while True:
        i = input(f'{q} (Y/n): ')
        if i == 'Y':
            return True
        elif i == 'n':
            return False

def parse_args():
    parser = argparse.ArgumentParser(
        prog="Modrinth Mod Manager (Emthree)",
        description="A CLI tool to automatically download and maintain Minecraft mods from Modrinth",
    )

    subparsers = parser.add_subparsers()
    parser_add = subparsers.add_parser('add')
    parser_init = subparsers.add_parser('init')
    parser_add.add_argument('mod', type=str)

    parser_init.add_argument("-u", "--userlist",
                        help="Path to CSV list containing mods")
    return parser.parse_args()

def load_userlist(list_path: Path) -> list[str]:
    if list_path.exists():
        try:
            with open(list_path, 'r') as f:
                userlist = []
                for l in f:
                    name = l.rstrip('\n')
                    if re.fullmatch("^[\\w!@$()`.+,\"\\-']{3,64}$", name):
                        userlist.append(name)
                    else:
                        logger.warning(f'Keyword {name} is not allowed. Check for typos. Exiting...')
                        return
        except Exception as e:
            logger.error(e)
        return userlist
    else: logger.warning(f'{Path} does not exist.')

def get_mod(query, game_version, is_slug) -> Mod:
    logger.info(f'fetching mod {query}')
    mod = Mod(query, game_version, is_slug)
    if mod.version_status in (VersionStatus.LEGACY_NONRELEASE_ONLY, VersionStatus.LEGACY_RELEASE, VersionStatus.LEGACY_NONRELEASE_W_RELEASE):
        logger.warning(f"{mod.slug} doesn't explicitly support {game_version}. Please check if it is maintained at https://modrinth.com/mod/{mod.slug}")
        if not prompt("Continue with no support for specified game version?"): return
    if mod.version_status == VersionStatus.UNAVAILABLE:
        logger.warning(f"{mod.slug} doesn't support fabric.")
        return
    if mod.version_status in (VersionStatus.LATEST_NONRELEASE_W_RELEASE, VersionStatus.LEGACY_NONRELEASE_W_RELEASE):
        logger.info(f"{mod.slug} has a newer {mod.version_alt['version_type']} \
            version {mod.version_alt['version_number']} compared to release version \
            {mod.version['version_number']}.")
        logger.info(f"Read changelogs here and make an informed decision. https://modrinth.com/mod/{mod.slug}")
        bleeding_edge = prompt(f"Use bleeding edge version?")
        if bleeding_edge: mod.use_alt()
    return mod

def batch_get_mod(batch_query: list[str], game_version: str, is_slug) -> list[Mod]:
    # since this uses multithreading, pass an API instance to prevent getting rate limited
    batch_mods: list[Mod] = []
    for i in batch_query:
        logger.info(f'fetching {i}...')
        batch_mods.append(get_mod(i, game_version, is_slug))
        logger.info(f'fetched {i}')
    return batch_mods

def batch_download(batch: list[Mod], install_dir: Path):
    for m in batch:
        path = m.install(install_dir)
    

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

import argparse, json, logging, re
from pathlib import Path
from platformdirs import user_config_dir, user_data_dir
from emthree.mod import Mod, VersionStatus

logger = logging.getLogger(__name__)

# modAPI = MODRINTH_API

def load_config(prod=True):
    if prod:
        config_path = Path(user_config_dir()) / 'emthree'
        if not config_path.is_dir():
            config_path.mkdir()
        config_file = Path(user_config_dir()) / 'emthree' / 'emthree-config.json'
        if config_file.is_file():
            with config_file.open('r') as f:
                return json.load(f)
        else:
            # create config file
            mod_path = input(f'Specify mod folder location: ')
            defaults = {
                "game" : {
                    "game_version": "1.21.11",
                    "mod_path": mod_path
                },
                "emthree" : {
                    "list_path": Path(user_data_dir()) / 'emthree'
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

async def get_mod(api_session, query: str, game_version: str, is_slug: bool, version_id: str = None) -> Mod:
    logger.info(f'fetching mod {query}')
    mod = Mod(api_session, query, game_version, is_slug, version_id=version_id)
    await mod.populate_data()
    logger.info(f'fetched mod {query}')
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
        if bleeding_edge: mod.use_alt(True)
        else: mod.use_alt(False)
    return mod

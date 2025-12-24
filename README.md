# Modrinth Mod Manager (Emthree)
is a user friendly CLI mod manager for Minecraft mods on Modrinth, written in Python.

## Features
- Convert user supplied list of mods into human readable JSON mod list
- Batch download arbitrary number of mods
- Automatically fetch mod information
- Detect and include dependencies

## Usage
On Linux, `emthree` will create/look for a `~/.config/emthree/emthree-config.json` which contains the following.

```json
{
    "game" : {
        "game_version": "1.21.11",
        "mod_path": PATH_TO_YOUR_MODS
    },
    "emthree" : {
        "list_path": ".local/share/emthree/"
    }
}
```

### Initial Usage
Use `emthree init -u userlist.txt` to download mods specified in `userlist.txt`, including any dependencies you might have missed. The `userlist.txt` (file extension optional) is a list of mod names separated by newlines. The correct names can be found from each mod's Modrinth URL, such as `https://modrinth.com/mod/fabric-api`. Data packs are not currently supported.

### Subsequent Usage
Running `emthree init` again will use the generated json file to download .jar files again. Running it with `-u` flag will ask you if you want to override the generated json file and start from scratch.

## Planned Features
- Fetch detailed information about individual mods
- Search mods
- Install/update/uninstall individual mods
- Neofetch inspired mod profile viewer (number of mods, game version, file size, etc.)
- Option to create a zip archive for easy sharing
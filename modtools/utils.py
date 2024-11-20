import csv
import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        prog="modtools",
        description="A CLI tool to automatically download and maintain Minecraft mods from Modrinth",
    )
    parser.add_argument("list_path",
                        help="Path to CSV list containing mods")
    parser.add_argument("-p", "--mod_path",
                        default="./mods",
                        help="Path to download mods to")
    parser.add_argument("-v", "--version",
                        default="1.21.1")
    parser.add_argument("-u", "--update")
    parser.add_argument("-i", "--install")

    return parser.parse_args()

def prompt(q):
    while True:
        i = input(f'{q} (Y/n): ')
        if i == 'Y':
            return True
        elif i == 'n':
            return False

def parse_user_list(path):
    prefix_a = "https://modrinth.com/mod/"
    prefix_b = "https://modrinth.com/datapack/"
    column_modrinth_link = 4
    column_server_side = 8
    modlist = []
    with open(path, "r", newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            if row[column_server_side] == "TRUE":
                modName = row[column_modrinth_link].replace(prefix_a, '').replace(prefix_b, '')
                modlist.append(modName)
                modlist = list(filter(None, modlist))
    return modlist
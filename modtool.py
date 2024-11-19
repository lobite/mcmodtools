import requests
import csv
import argparse
import time
import concurrent.futures

class modrinthAPI:
    def __init__(self):
        self.API = "https://api.modrinth.com/v2/"
        self.reqCount = 0
        self.maxCalls = 300
        self.accessTime = time.time_ns()
        self.minute = 60 * 10 ** 9

    def rateLimit(self):
        self.reqCount += 1
        if self.reqCount == 1:
            self.accessTime = time.time_ns()
        elapsed = time.time_ns() - self.accessTime
        if elapsed < self.minute and self.reqCount >= self.maxCalls:
            print("Rate limited... pausing")
            self.reqCount = 0
            time.sleep(self.minute - elapsed)
            print("resumed")
        elif elapsed >= self.minute:
            self.reqCount = 0

    def get(self, url):
        try:
            self.rateLimit()
            r = requests.get(self.API + url)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as err:
            raise err

    def download(self, url, path):
        try:
            self.rateLimit()
            c = requests.get(url)
            c.raise_for_status()
            open(path, "xb").write(c.content)
        except requests.exceptions.RequestException as err:
            raise err

    def version(self, modID):
        url = f'project/{modID}/version'
    def checkDependencies(self, modID):
        url = f'project/{modID}/dependencies'
        res = self.get(url)
        dependencies = []
        for dep in res["projects"]:
            dependencies.append(dep["project_id"])
        return dependencies

modAPI = modrinthAPI()

def parseArgs():
    parser = argparse.ArgumentParser(
        prog="modtools",
        description="A CLI tool to automatically download and maintain Minecraft mods from Modrinth",
    )
    parser.add_argument("listPath",
                        help="Path to CSV list containing mods")
    parser.add_argument("-p", "--modpath",
                        default="./mods",
                        help="Path to download mods to")
    parser.add_argument("-v", "--version",
                        default="1.21.1")
    parser.add_argument("-u", "--update")
    parser.add_argument("-i", "--install")

    return parser.parse_args()

args = parseArgs()


def parseUserModList(path):
    prefixA = "https://modrinth.com/mod/"
    prefixB = "https://modrinth.com/datapack/"
    columnModrinthLink = 4
    columnServerSide = 8
    modList = []
    with open(path, "r", newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            if row[columnServerSide] == "TRUE":
                modName = row[columnModrinthLink].replace(prefixA, '').replace(prefixB, '')
                modList.append(modName)
                modList = list(filter(None, modList))
    return modList

def idfyUserModList(modList):
    ids = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for mod in modList:
            futures.append(executor.submit(modAPI.get, url=f'project/{mod}'))
        for future in concurrent.futures.as_completed(futures):
            id = future.result()["id"]
            ids.append(id)
        
    return ids

def loadMods(idList):
    pass


# TODO: Create generated list file for faster access, only load CSV if file is missing

collection = idfyUserModList(parseUserModList(args.listPath))
print(collection)
print(modAPI.reqCount)
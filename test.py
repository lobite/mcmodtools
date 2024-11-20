import requests
API = "https://api.modrinth.com/v2/"

r = requests.get(API + 'project/diagonal-fences/dependencies')
body = r.json()

# print(body["projects"][0])
print(body["versions"][0])
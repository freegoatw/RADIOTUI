from api import radio_browser as rb
import sys


dat = rb.GetByName("justin")
totalStations = len(dat)
if totalStations == 0:
    print("No Staions found")

for indx, i in enumerate(dat):
    print(f"{indx:2}. {i.get('name')[:48]:<60} | {i.get('country')}")


# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

import openrouteservice
import json

client = openrouteservice.Client(key='eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjYyZDliMWU4MWQ2NTRiZGE5OWExMWU1ZTcwMDIzOWZjIiwiaCI6Im11cm11cjY0In0=')

def GeoLocate():
    # To use the coordinates here you need to flip it around for Google Maps to work
    # Geolocation of Starting Address
    BothCoordinatesExist = True
    print("Enter Starting Address : ", end="")
    startingAddress = input();

    geocoderesult1 = client.pelias_search(text=startingAddress)

    if geocoderesult1['features']:
        startcoordinates = geocoderesult1['features'][0]['geometry']['coordinates']
        print(f"Coordinates for '{startingAddress}': {startcoordinates} \n")
    else:
        BothCoordinatesExist = False
        print("No results found for the given place. \n")


    #Geolocation of Ending Address
    print("Enter Dropoff Address : ", end="")
    endingAddress = input();

    geocoderesult2 = client.pelias_search(text=endingAddress)

    if geocoderesult2['features']:
        endcoordinates = geocoderesult2['features'][0]['geometry']['coordinates']
        print(f"Coordinates for '{endingAddress}': {endcoordinates} \n")
    else:
        BothCoordinatesExist = False
        print("No results found for the given place. \n")

    if BothCoordinatesExist:
        route = client.directions(
            coordinates=[startcoordinates,endcoordinates],
            profile='driving-car',
            format='geojson'
        )

        distance_meters = route['features'][0]['properties']['summary']['distance']
        duration_seconds = route['features'][0]['properties']['summary']['duration']

        print(f"Distance: {distance_meters / 1000:.2f} km")
        print(f"Duration: {duration_seconds / 60:.1f} minutes \n")

        rideFare = 3 + (distance_meters / 1000) + ((duration_seconds / 60)*0.5)
        print(f"Ride Fare: RM{rideFare:.2f} \n")

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    GeoLocate()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/

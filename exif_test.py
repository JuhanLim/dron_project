from exif import Image

# Load an image with GPS data
with open(r'C:\Users\v\Desktop\dron_project\test_image\A3_T1_W1_H1_S102_1_20211022_103546_0108.jpg', 'rb') as img_file:
    img = Image(img_file)

# Check if GPS information is available
if img.has_exif and 'gps_latitude' in img.list_all():
    # Extract GPS data
    latitude = img.gps_latitude
    longitude = img.gps_longitude
    print(f'GPS Coordinates: {latitude}, {longitude}')
else:
    print('No GPS data found in the image.')
import exif

def get_gps_info(image_path):
    """Extract and print GPS coordinates from an image using EXIF metadata."""
    with open(image_path, 'rb') as img_file:
        img = exif.Image(img_file)

    if not img.has_exif:
        print("No EXIF metadata found.")
        return None

    if 'gps_latitude' not in img.list_all():
        print("No GPS data found.")
        return None

    def to_decimal(coords, ref):
        decimal = coords[0] + coords[1] / 60 + coords[2] / 3600
        return -decimal if ref in ['S', 'W'] else decimal

    latitude = to_decimal(img.gps_latitude, img.gps_latitude_ref)
    longitude = to_decimal(img.gps_longitude, img.gps_longitude_ref)

    print(f"Latitude: {latitude}, Longitude: {longitude}")
    return (latitude, longitude)

# Test with your uploaded image
image_path = r"C:\Users\v\Desktop\dron_project\dron_project\downloads\A3_T1_W1_H1_S102_1_20211022_103546_0108.jpg"
get_gps_info(image_path)
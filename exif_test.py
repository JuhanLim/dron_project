import os
import glob
import csv
import piexif
from PIL import Image

def convert_to_deg(value, ref):
    """Convert GPS coordinates to degrees format required by EXIF."""
    degrees = int(value)
    minutes = int((value - degrees) * 60)
    seconds = int((value - degrees - minutes / 60) * 3600 * 1000)
    return ((degrees, 1), (minutes, 1), (seconds, 1000)), ref

def add_gps_and_orientation_to_exif(img_path, latitude, longitude, altitude, roll, pitch, yaw):
    """Add GPS and orientation data to a JPEG image."""
    img = Image.open(img_path)

    # Load existing EXIF data or initialize a new dictionary
    try:
        exif_dict = piexif.load(img.info.get('exif', b''))
    except Exception as e:
        print(f"EXIF Load Error for {img_path}: {e}")
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}

    # Convert latitude and longitude
    lat_deg, lat_ref = convert_to_deg(abs(latitude), 'N' if latitude >= 0 else 'S')
    lon_deg, lon_ref = convert_to_deg(abs(longitude), 'E' if longitude >= 0 else 'W')

    # Prepare GPS data
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: lat_deg,
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: lon_deg,
        piexif.GPSIFD.GPSAltitudeRef: 0 if altitude >= 0 else 1,
        piexif.GPSIFD.GPSAltitude: (abs(int(altitude * 1000)), 1000)
    }

    exif_dict['GPS'] = gps_ifd

    # Add roll, pitch, yaw in EXIF "UserComment" or "ImageDescription" (not standardized fields)
    user_comment = f"Roll={roll},Pitch={pitch},Yaw={yaw}"
    exif_dict['Exif'][piexif.ExifIFD.UserComment] = user_comment.encode('utf-16')

    exif_bytes = piexif.dump(exif_dict)
    img.save(img_path, 'jpeg', exif=exif_bytes)

def process_image_csv_pairs(images_dir, csv_dir):
    """Match each image with its corresponding CSV file and update EXIF data."""
    image_files = glob.glob(os.path.join(images_dir, "*.jpg"))

    for image_file in image_files:
        image_basename = os.path.splitext(os.path.basename(image_file))[0]
        csv_file = os.path.join(csv_dir, f"{image_basename}.csv")

        if not os.path.exists(csv_file):
            print(f"CSV file not found for image {image_file}")
            continue

        try:
            with open(csv_file, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                row = next(reader)
                latitude = float(row['gps_raw_int__lat'])
                longitude = float(row['gps_raw_int__lon'])
                altitude = float(row['gps_raw_int__alt'])
                roll = float(row['attitude__roll'])
                pitch = float(row['attitude__pitch'])
                yaw = float(row['attitude__yaw'])

                add_gps_and_orientation_to_exif(image_file, latitude, longitude, altitude, roll, pitch, yaw)
                print(f"GPS and Orientation data added to {image_file}")

        except Exception as e:
            print(f"Error processing {image_file}: {e}")


# Example usage
images_dir = r'C:\Users\v\Desktop\dron_project\test_image'  # Directory containing the JPEG images
csv_dir = r'C:\Users\v\Desktop\dron_project\test_image'  # Directory containing the CSV files

process_image_csv_pairs(images_dir, csv_dir)

# 처음부터 EXIF 이미지가 아닌겨우 b 에러가 발생함. 초기화 해주었음 
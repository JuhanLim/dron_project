from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
import boto3
from botocore.exceptions import NoCredentialsError
import os 
from .yolo import predict_yolo
import csv
import piexif
from PIL import Image
import tempfile 
import boto3
import glob
import cv2
import exif

class UploadFilesToS3(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist('files[]')
        uploaded_files = []
        csv_data = {}
        
        # Configure Boto3 Client
        s3_client = boto3.client(
            's3',
            region_name=settings.NAVER_CLOUD_REGION,
            endpoint_url=settings.NAVER_CLOUD_ENDPOINT,
            aws_access_key_id=settings.NAVER_CLOUD_ACCESS_KEY,
            aws_secret_access_key=settings.NAVER_CLOUD_SECRET_KEY
        )

        # Separate CSV and image files
        csv_files = [f for f in files if f.name.lower().endswith('.csv')]
        image_files = [f for f in files if f.name.lower().endswith(('.jpg', '.jpeg', '.png'))]
        # Parse CSV files for GPS data
        for csv_file in csv_files:
            csv_name = os.path.splitext(csv_file.name)[0]
            csv_reader = csv.DictReader(csv_file.read().decode('utf-8').splitlines())
            for row in csv_reader:
                csv_data[csv_name] = {
                    'latitude': float(row.get('gps_raw_int__lat', 0)),
                    'longitude': float(row.get('gps_raw_int__lon', 0)),
                    'altitude': float(row.get('gps_raw_int__alt', 0)),
                    'roll': float(row.get('attitude__roll', 0)),
                    'pitch': float(row.get('attitude__pitch', 0)),
                    'yaw': float(row.get('attitude__yaw', 0))
                }
        # 업로드 할때 GPS 정보를 삽입해서 클라우드에 업로드. 
        def add_gps_to_exif(img, gps_info):
            """Add GPS data to an image."""
            exif_dict = piexif.load(img.info.get('exif', b''))
            lat_deg, lat_ref = convert_to_deg(abs(gps_info['latitude']), 'N' if gps_info['latitude'] >= 0 else 'S')
            lon_deg, lon_ref = convert_to_deg(abs(gps_info['longitude']), 'E' if gps_info['longitude'] >= 0 else 'W')
            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: lat_ref,
                piexif.GPSIFD.GPSLatitude: lat_deg,
                piexif.GPSIFD.GPSLongitudeRef: lon_ref,
                piexif.GPSIFD.GPSLongitude: lon_deg,
                piexif.GPSIFD.GPSAltitudeRef: 0 if gps_info['altitude'] >= 0 else 1,
                piexif.GPSIFD.GPSAltitude: (abs(int(gps_info['altitude'] * 1000)), 1000)
            }
            exif_dict['GPS'] = gps_ifd
            exif_bytes = piexif.dump(exif_dict)
            return exif_bytes
        def convert_to_deg(value, ref):
            degrees = int(value)
            minutes = int((value - degrees) * 60)
            seconds = int((value - degrees - minutes / 60) * 3600 * 1000)
            return ((degrees, 1), (minutes, 1), (seconds, 1000)), ref
        
        
        for image_file in image_files:
            image_name = os.path.splitext(image_file.name)[0]
            gps_info = csv_data.get(image_name)

            if gps_info:
                img = Image.open(image_file)
                exif_bytes = add_gps_to_exif(img, gps_info)
                
                #이미지 임시 저장 ( c://tmp 폴더는 사용할 수 없었음 )
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    local_image_path = tmp_file.name
                    img.save(local_image_path, 'jpeg', exif=exif_bytes)

                # Upload to Naver Cloud
                try:
                    s3_client.upload_file(local_image_path, settings.NAVER_CLOUD_BUCKET, image_file.name)
                    uploaded_files.append(image_file.name)
                except Exception as e:
                    return Response({'message': str(e)}, status=500)

        return Response({'message': 'Files uploaded successfully', 'files': uploaded_files}, status=200)
    
class DownloadAndProcessImage(APIView):
    def post(self, request, *args, **kwargs):
        file_key = request.data.get('file_key')

        if not file_key:
            return Response({'message': 'No file key provided'}, status=400)

        # Configure Boto3 Client for Naver Cloud Storage
        s3_client = boto3.client(
            's3',
            region_name=settings.NAVER_CLOUD_REGION,
            endpoint_url=settings.NAVER_CLOUD_ENDPOINT,
            aws_access_key_id=settings.NAVER_CLOUD_ACCESS_KEY,
            aws_secret_access_key=settings.NAVER_CLOUD_SECRET_KEY
        )

        dron_bucket = settings.NAVER_CLOUD_BUCKET
        result_bucket = settings.NAVER_CLOUD_RESULT_BUCKET
        local_images_dir = 'downloads'
        panorama_output_dir = 'panorama'
        os.makedirs(local_images_dir, exist_ok=True)
        os.makedirs(panorama_output_dir, exist_ok=True)

        # Fetch All Images from dron-image Bucket
        def fetch_images_from_s3(bucket_name, local_dir):
            objects = s3_client.list_objects_v2(Bucket=bucket_name).get('Contents', [])
            for obj in objects:
                key = obj['Key']
                local_path = os.path.join(local_dir, os.path.basename(key))
                try:
                    s3_client.download_file(bucket_name, key, local_path)
                    print(f'Downloaded: {local_path}')
                except Exception as e:
                    print(f"Failed to download {key}: {e}")

        # Extract GPS Data from Images
        def get_gps_data(image_path):
            """Extract GPS coordinates from an image using EXIF metadata."""
            print(f"Extracting GPS data from: {image_path}")
            if not os.path.exists(image_path):
                print(f"File not found: {image_path}")
                return None

            try:
                with open(image_path, 'rb') as img_file:
                    img = exif.Image(img_file)

                if not img.has_exif or 'gps_latitude' not in img.list_all():
                    return None

                def to_decimal(coords, ref):
                    decimal = coords[0] + coords[1] / 60 + coords[2] / 3600
                    return -decimal if ref in ['S', 'W'] else decimal

                latitude = to_decimal(img.gps_latitude, img.gps_latitude_ref)
                longitude = to_decimal(img.gps_longitude, img.gps_longitude_ref)

                return (latitude, longitude)
            except Exception as e:
                print(f"Error reading GPS data from {image_path}: {e}")
                return None

        # Read and Store GPS Data
        def read_and_store_gps_data(images):
            """Read and store GPS data for images before resizing."""
            gps_data = {}
            for img in images:
                gps_info = get_gps_data(img)
                if gps_info is not None:
                    gps_data[os.path.basename(img)] = gps_info
            return gps_data

        # Approximate Image Positions Using Stored GPS Data
        def approximate_image_positions_with_gps(images, gps_data):
            """Approximate image positions based on stored GPS data."""
            gps_positions = [(img, gps_data.get(os.path.basename(img))) for img in images]
            gps_positions = [(img, data) for img, data in gps_positions if data is not None]

            if not gps_positions:
                raise ValueError("No GPS data found in the provided images!")

            # Sort images by latitude and then by longitude
            gps_positions.sort(key=lambda x: (x[1][0], x[1][1]))
            return [img for img, _ in gps_positions]

        # Resize Images Without Losing GPS Data
        def resize_images(images_dir, output_dir, max_width=1024): # 메모리 아웃 떠서 2000 에서 1024 로 조정 
            """Resize images to a smaller size."""
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            image_files = glob.glob(os.path.join(images_dir, "*.jpg"))
            resized_images = []

            for image_file in image_files:
                img = cv2.imread(image_file)
                height, width = img.shape[:2]

                if width > max_width:
                    aspect_ratio = height / width
                    new_width = max_width
                    new_height = int(new_width * aspect_ratio)
                    img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

                resized_path = os.path.join(output_dir, os.path.basename(image_file))
                cv2.imwrite(resized_path, img)
                resized_images.append(resized_path)

            return resized_images

        # Create Panorama Using OpenCV
        def create_opencv_panorama(images_dir, output_file, gps_data, use_opencl=False):
            """Create a panorama using OpenCV's Stitcher class."""
            cv2.ocl.setUseOpenCL(use_opencl)  # Disable OpenCL if needed
            resized_images_dir = os.path.join(images_dir, "resized")
            if not os.path.exists(resized_images_dir):
                os.makedirs(resized_images_dir, exist_ok=True)

            resized_images = resize_images(images_dir, resized_images_dir)
            sorted_images = approximate_image_positions_with_gps(resized_images, gps_data)

            images = [cv2.imread(img) for img in sorted_images]
            stitcher = cv2.Stitcher_create() if int(cv2.__version__[0]) >= 4 else cv2.createStitcher()
            stitcher.setPanoConfidenceThresh(0.8)

            status, panorama = stitcher.stitch(images)

            if status != cv2.Stitcher_OK:
                print("Stitching failed with status code:", status)
                return None

            cv2.imwrite(output_file, panorama)
            print(f"Panorama saved to: {output_file}")
            return output_file


        # 파일 다운로드 하기 
        fetch_images_from_s3(dron_bucket, local_images_dir)
        # Read and store GPS data from original images
        original_images = glob.glob(os.path.join(local_images_dir, "*.jpg"))
        gps_data = read_and_store_gps_data(original_images)
        # 파노라마 만들기 시작 
        stitched_panorama = create_opencv_panorama(local_images_dir, os.path.join(panorama_output_dir, 'stitched_panorama.jpg'), gps_data)
        if not stitched_panorama:
            return Response({'message': 'Panorama creation failed'}, status=500)

        # 파노라마 결과물에 대해 yolo 작업 시작 
        processed_panorama = predict_yolo(stitched_panorama)

        try:
            s3_client.upload_file(processed_panorama, result_bucket, os.path.basename(processed_panorama))
        except Exception as e:
            return Response({'message': str(e)}, status=500)

        return Response({'message': 'Panorama created, processed, and uploaded successfully'}, status=200)
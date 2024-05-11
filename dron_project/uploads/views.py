from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import JsonResponse # 클라우드 이미지를 로컬에 받지 않기 위한
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
import numpy as np


# naver cloud 인증 정보
s3_client = boto3.client(
    's3',
    region_name=settings.NAVER_CLOUD_REGION,
    endpoint_url=settings.NAVER_CLOUD_ENDPOINT,
    aws_access_key_id=settings.NAVER_CLOUD_ACCESS_KEY,
    aws_secret_access_key=settings.NAVER_CLOUD_SECRET_KEY
)
dron_bucket = settings.NAVER_CLOUD_BUCKET
result_bucket = settings.NAVER_CLOUD_RESULT_BUCKET


class UploadFilesToS3(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist('files[]')
        uploaded_files = []
        csv_data = {}


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

        # Convert GPS information to EXIF
        def add_gps_to_exif(img, gps_info):
            """Add GPS data to an image."""
            exif_dict = piexif.load(img.info.get('exif', b'') or piexif.dump({}) )
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

        # Resize Image using OpenCV
        def resize_image_opencv(image_file, max_width=720):
            """가로 세로 비율을 유지하면서 영상 크기를 최대 너비로 조정합니다."""
            # Pillow로 이미지 읽기
            img = Image.open(image_file)

            # Pillow 이미지를 numpy 배열로 변환
            img_np = np.array(img)

            # numpy 배열을 통해 OpenCV 형식으로 변환
            if len(img_np.shape) == 2:
                # 흑백 이미지인 경우
                height, width = img_np.shape
            else:
                height, width, _ = img_np.shape
            print("높이,넓이 : " , height, width)
            # 최대 너비로 조정
            if width > max_width:
                aspect_ratio = height / width
                new_width = max_width
                new_height = int(new_width * aspect_ratio)
                img_np = cv2.resize(img_np, (new_width, new_height), interpolation=cv2.INTER_AREA)

            # 이미지 회전
            img_np = cv2.rotate(img_np, cv2.ROTATE_90_COUNTERCLOCKWISE)
            # Pillow 형식으로 변환하여 반환
            img_resized = Image.fromarray(img_np)
            return img_resized

        # Process and upload images
        for image_file in image_files:
            image_name = os.path.splitext(image_file.name)[0]
            gps_info = csv_data.get(image_name)

            if gps_info:
                img = resize_image_opencv(image_file)  # Resize image before adding EXIF
                exif_bytes = add_gps_to_exif(img, gps_info)

                # Save image temporarily
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    local_image_path = tmp_file.name
                    img.save(local_image_path, 'jpeg', exif=exif_bytes)

                # Upload to Naver Cloud
                try:
                    s3_client.upload_file(local_image_path, settings.NAVER_CLOUD_BUCKET, image_file.name)
                    uploaded_files.append(image_file.name)
                except Exception as e:
                    return Response({'message': str(e)}, status=500)
                finally:
                    os.remove(local_image_path)

        return Response({'message': 'Files uploaded successfully', 'files': uploaded_files}, status=200)
    
class DownloadAndProcessImage(APIView):
    def post(self, request, *args, **kwargs):
        file_key = request.data.get('file_key')

        if not file_key:
            return Response({'message': 'No file key provided'}, status=400)

        # dron_bucket = settings.NAVER_CLOUD_BUCKET
        # result_bucket = settings.NAVER_CLOUD_RESULT_BUCKET
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
            """Read and store GPS data for images before stitching."""
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

        # Create Panorama Using OpenCV
        def create_opencv_panorama(images_dir, output_file, gps_data, use_opencl=False):
            """Create a panorama using OpenCV's Stitcher class."""
            
            cv2.ocl.setUseOpenCL(use_opencl)  # 메모리 초과로 opencl 설정 
            image_files = glob.glob(os.path.join(images_dir, "*.jpg"))
            sorted_images = approximate_image_positions_with_gps(image_files, gps_data)
            processed_images = []
            for img_path in sorted_images:
                processed_img_path = predict_yolo(img_path)
                processed_images.append(processed_img_path)
            
            print("sorted_images : " ,sorted_images)
            images = [cv2.imread(img) for img in processed_images]
            stitcher = cv2.Stitcher_create() if int(cv2.__version__[0]) >= 4 else cv2.createStitcher()
            stitcher.setPanoConfidenceThresh(0.8)  # Adjust as necessary
            # stitcher.setSeamFinder(cv2.detail_NoSeamFinder()) 없음. cv2.detail 을 직접 사용해야함
            print("파노라마 시작")
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
        #processed_panorama = predict_yolo(stitched_panorama)

        try:
            s3_client.upload_file(stitched_panorama, result_bucket, os.path.basename(stitched_panorama))
        except Exception as e:
            return Response({'message': str(e)}, status=500)

        return Response({'message': 'Panorama created, processed, and uploaded successfully'}, status=200)
    
class FetchImagesFromS3(APIView):
    def get(self, request, *args, **kwargs):
        try:
            # Retrieve the list of objects in the bucket
            response = s3_client.list_objects_v2(Bucket=result_bucket)
            images = []
            if 'Contents' in response:
                for item in response['Contents']:
                    key = item['Key']
                    # Generate a presigned URL for each image
                    url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': result_bucket, 'Key': key},
                        ExpiresIn=3600  # The URL expires in one hour
                    )
                    images.append({'filename': key, 'url': url})
            return JsonResponse({'images': images}, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
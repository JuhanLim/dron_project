from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
import boto3
from botocore.exceptions import NoCredentialsError
import os 
from yolo import predict_yolo

class UploadFilesToS3(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist('files[]')
        uploaded_files = []

        # Configure Boto3 Client
        s3_client = boto3.client(
            's3',
            region_name=settings.NAVER_CLOUD_REGION,
            endpoint_url=settings.NAVER_CLOUD_ENDPOINT,
            aws_access_key_id=settings.NAVER_CLOUD_ACCESS_KEY,
            aws_secret_access_key=settings.NAVER_CLOUD_SECRET_KEY
        )

        for file in files:
            file_key = file.name
            try:
                s3_client.upload_fileobj(file, settings.NAVER_CLOUD_BUCKET, file_key)
                uploaded_files.append(file_key)
            except NoCredentialsError:
                return Response({'message': 'Credentials not available'}, status=400)
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

        # Download the image to a local directory
        download_path = os.path.join('downloads', file_key)
        os.makedirs('downloads', exist_ok=True)

        try:
            s3_client.download_file(settings.NAVER_CLOUD_BUCKET, file_key, download_path)
        except Exception as e:
            return Response({'message': str(e)}, status=500)

        processed_img_path = predict_yolo(download_path)
        
        # Process the image with YOLOv5
        try:
            s3_client.upload_file(processed_img_path, settings.NAVER_CLOUD_RESULT_BUCKET, os.path.basename(processed_img_path))
        except Exception as e:
            return Response({'message': str(e)}, status=500)

        return Response({'message': 'File downloaded, processed, and uploaded successfully', 'file_key': file_key}, status=200)

    
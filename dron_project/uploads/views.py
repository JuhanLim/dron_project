from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
import boto3
from botocore.exceptions import NoCredentialsError

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
from django.urls import path
from .views import UploadFilesToS3

urlpatterns = [
    path('upload/', UploadFilesToS3.as_view(), name='upload-files-to-s3'),
]
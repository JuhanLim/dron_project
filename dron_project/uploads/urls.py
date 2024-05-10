from django.urls import path
from .views import UploadFilesToS3,DownloadAndProcessImage

urlpatterns = [
    path('upload/', UploadFilesToS3.as_view(), name='upload-files-to-s3'),
    path('download-and-process/', DownloadAndProcessImage.as_view(), name='download-and-process-image')
]
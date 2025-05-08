
from django.contrib import admin
from django.urls import path
from user.views import MyTokenObtainPairView,MailItemUpdateStatus,CheckMailItemAPIView,FaceRecognitionAPIView
from rest_framework_simplejwt.views import TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('management/admin/', admin.site.urls),
    path('api/v1/face-recognition/', FaceRecognitionAPIView.as_view(), name='face-recognition'),
    path('api/v1/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/order/',MailItemUpdateStatus.as_view(), name="update-status"),
    path('api/v1/check-mail/', CheckMailItemAPIView.as_view(), name='check-mail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

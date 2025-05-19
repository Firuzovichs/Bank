
from django.contrib import admin
from django.urls import path
from user.views import MyTokenObtainPairView,MailItemUpdateStatus,MailItemAllListView,BatchStatisticsAPIView,CheckMailItemAPIView,FaceRecognitionAPIView,MailItemStatsAPIView,ReceivedDateMonthCountView,DeliveredMailItemListView
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
    path('api/v1/dashboard-status/', MailItemStatsAPIView.as_view(), name='dash-status'),
    path('api/v1/dashboard-months/', ReceivedDateMonthCountView.as_view(), name='dash-months'),
    path('api/v1/checked-mails/', DeliveredMailItemListView.as_view(), name='checked-mails'),
    path('api/v1/batch-status/', BatchStatisticsAPIView.as_view(), name='batch-status'),
    path('api/v1/mails-all/', MailItemAllListView.as_view(), name='mails-all'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

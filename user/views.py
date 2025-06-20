from django.shortcuts import render
from .serializers import TokenObtainPairSerializer,BankUsersProfileSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from django.utils import timezone
import numpy as np
import face_recognition
from django.db.models import Sum, Count
from rest_framework import status
from .models import MailItem
from PIL import Image
from .models import BankUsers,Region,District
from django.db.models.functions import TruncMonth
import calendar
from django.db.models import Count
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import ListAPIView
from .serializers import MailItemSerializer,CheckedMailItemSerializer
from collections import Counter
from django.db.models import Q
import base64
from io import BytesIO
import base64
import uuid
from django.core.files.base import ContentFile

class MailItemPagination(PageNumberPagination):
    page_size = 10  # Har bir sahifada 10 ta element chiqadi
    page_size_query_param = 'page_size'
    max_page_size = 100



class CheckedMailItemsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        queryset = MailItem.objects.filter(is_check=True).order_by('-checked_time')
        paginator = MailItemPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = CheckedMailItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)



class FaceRecognitionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        base64_image = request.data.get('photo')
        if not base64_image:
            return Response({'error': 'Rasm jo‘natilmagan'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if "base64," in base64_image:
                base64_image = base64_image.split("base64,")[1]

            decoded_image = base64.b64decode(base64_image)
            image = Image.open(BytesIO(decoded_image)).convert("RGB")
            img_np = np.array(image)

            # Yuzni aniqlash va embedding olish
            face_locations = face_recognition.face_locations(img_np)
            if not face_locations:
                return Response({'error': 'Yuz aniqlanmadi'}, status=status.HTTP_400_BAD_REQUEST)

            face_encodings = face_recognition.face_encodings(img_np, face_locations)
            input_encoding = face_encodings[0]

            matched_user = None

            for profile in BankUsers.objects.all():
                if not profile.photo:
                    continue

                profile_img = Image.open(profile.photo.path).convert("RGB")
                profile_np = np.array(profile_img)

                profile_face_locations = face_recognition.face_locations(profile_np)
                if not profile_face_locations:
                    continue

                profile_encodings = face_recognition.face_encodings(profile_np, profile_face_locations)
                if not profile_encodings:
                    continue

                profile_encoding = profile_encodings[0]

                match_results = face_recognition.compare_faces([profile_encoding], input_encoding, tolerance=0.5)
                if match_results[0]:
                    matched_user = profile
                    break

            if matched_user:
                return Response({
                    'token': matched_user.token,
                    'phone_number': matched_user.phone_number
                }, status=status.HTTP_200_OK)

            return Response({'message': 'Mos foydalanuvchi topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BatchStatsView(APIView):
    permission_classes = [IsAuthenticated]  # Bu API uchun autentifikatsiya talab qilinadi

    def get(self, request):
        # Request parametridan batch filtri olish
        batch_filter = request.GET.get('batch')  # Batch parametri

        # Agar batch parametri kiritilgan bo'lsa, faqat shu batch bo'yicha filtrlanadi
        if batch_filter:
            batches = MailItem.objects.filter(batch=batch_filter).values('batch').distinct()
        else:
            # Agar batch filtri bo'lmasa, barcha batchlarni olish
            batches = MailItem.objects.values('batch').distinct()

        batch_stats = []
        for batch in batches:
            batch_name = batch['batch']
            # Har bir batchga tegishli RZ va CZ bilan boshlanadigan barcodelarni ajratish
            rz_items = MailItem.objects.filter(batch=batch_name, barcode__startswith='RZ')
            cz_items = MailItem.objects.filter(batch=batch_name, barcode__startswith='CZ')

            # RZ va CZ bo‘yicha statistikani olish
            rz_count = rz_items.count()  # RZ bilan boshlanadigan barcodelar soni
            cz_count = cz_items.count()  # CZ bilan boshlanadigan barcodelar soni

            rz_weight_sum = rz_items.aggregate(Sum('weight'))['weight__sum'] or 0  # RZ weightlari yig‘indisi
            cz_weight_sum = cz_items.aggregate(Sum('weight'))['weight__sum'] or 0  # CZ weightlari yig‘indisi

            # Batch uchun statistikani qo‘shish
            batch_stats.append({
                'batch': batch_name,
                'rz_count': rz_count,
                'cz_count': cz_count,
                'rz_weight_sum': rz_weight_sum,
                'cz_weight_sum': cz_weight_sum
            })

        return Response(batch_stats, status=status.HTTP_200_OK)


class BatchStatisticsAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Bu API uchun autentifikatsiya talab qilinadi

    def get(self, request):
        # Request parametridan batch filtri olish
        batch_filter = request.GET.get('batch')  # Batch parametri

        # Agar batch parametri kiritilgan bo'lsa, faqat shu batch bo'yicha filtrlanadi
        if batch_filter:
            batches = MailItem.objects.filter(batch=batch_filter).values("batch").distinct()
        else:
            # Agar batch filtri bo'lmasa, barcha batchlarni olish
            batches = MailItem.objects.values("batch").distinct()

        # Barcha batchlar bo‘yicha weight yig‘indisini hisoblash
        batch_stats = (
            batches
            .annotate(total_count=Count("barcode"))  # Har bir batch bo‘yicha barcode soni
        )

        # Har bir batch uchun natijani saqlash
        result = {}

        for batch in batch_stats:
            batch_name = batch["batch"]
            total_count = batch["total_count"]

            items = MailItem.objects.filter(batch=batch_name)

            status_counter = Counter()

            for item in items:
                if item.last_event_name:  
                    last_status = item.last_event_name[-1]  # Oxirgi elementni olish
                    status_counter[last_status] += 1

            # Natijalarni batch bo‘yicha saqlash
            result[batch_name] = {
                "total_count": total_count,
                "status_counts": status_counter  # Har bir batch uchun statuslar
            }

        return Response({"batch_statistics": result})


class MailItemAllListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = Q()
        user = request.user

        # Foydalanuvchining viloyat yoki tuman maydonlarini tekshirish
        if user.tuman:
            filters &= Q(district=user.tuman)
        elif user.viloyat:
            filters &= Q(region=user.viloyat)
        else:
            return Response({"error": "Foydalanuvchi tuman yoki viloyat bilan bog‘lanmagan"}, status=400)

        # Qo‘shimcha query parametrlarga asoslangan filterlar
        batch = request.GET.get('batch')
        if batch:
            filters &= Q(batch__icontains=batch)

        barcode = request.GET.get('barcode')
        if barcode:
            filters &= Q(barcode__icontains=barcode)

        weight = request.GET.get('weight')
        if weight:
            try:
                weight = float(weight)
                filters &= Q(weight=weight)
            except ValueError:
                return Response({"error": "Noto‘g‘ri weight qiymati"}, status=400)

        city = request.GET.get('city')
        if city:
            filters &= Q(city__icontains=city)

        date_fields = ['send_date', 'received_date', 'last_event_date']
        for field in date_fields:
            date_value = request.GET.get(field)
            if date_value:
                filters &= Q(**{f"{field}": date_value})
            from_date = request.GET.get(f"{field}_from")
            if from_date:
                filters &= Q(**{f"{field}__gte": from_date})
            to_date = request.GET.get(f"{field}_to")
            if to_date:
                filters &= Q(**{f"{field}__lte": to_date})

        # MailItemlarni olish
        mail_items = MailItem.objects.filter(filters).order_by('-updated_at')

        # last_event_name bo‘yicha filtr
        last_event_name = request.GET.get('last_event_name')
        if last_event_name:
            mail_items = [item for item in mail_items if item.last_event_name and item.last_event_name[-1] == last_event_name]

        # Sahifalash
        paginator = MailItemPagination()
        paginated_mail_items = paginator.paginate_queryset(mail_items, request)
        serializer = MailItemSerializer(paginated_mail_items, many=True)
        return paginator.get_paginated_response(serializer.data)

class DeliveredMailItemListView(ListAPIView):
    serializer_class = MailItemSerializer
    pagination_class = MailItemPagination

    def get_queryset(self):
        return MailItem.objects.filter(is_delivered=True).order_by('-send_date')
    

class MailItemStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        first_name = user.first_name
        last_name = user.last_name

        # Faqat city = user.first_name bo'lgan MailItemlar
        queryset = MailItem.objects.filter(city=first_name)
        total = queryset.count()

        completed = queryset.filter(last_event_name__contains="completed").count()
        return_status = queryset.filter(last_event_name__contains="returning_to_origin").count()
        other_count = total - completed - return_status

        def percentage(count):
            return round((count / total) * 100, 2) if total > 0 else 0

        return Response({
            "total_items": {
                "count": total,
                "percent": "100%"
            },
            "on_way_items": {
                "count": completed,
                "percent": f"{percentage(completed)}%"
            },
            "return": {
                "count": return_status,
                "percent": f"{percentage(return_status)}%"
            },
            "other_items": {
                "count": other_count,
                "percent": f"{percentage(other_count)}%"
            }
        })


class ReceivedDateMonthCountView(APIView):
    def get(self, request):
        result = (
            MailItem.objects
            .filter(received_date__isnull=False)  # <--- null qiymatlar tashlab yuboriladi
            .annotate(month=TruncMonth('received_date'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('-month')
        )

        result_with_names = []
        for item in result:
            month_name = calendar.month_name[item['month'].month]
            result_with_names.append({
                "month": month_name,
                "year": item['month'].year,
                "count": item['count']
            })

        return Response(result_with_names, status=status.HTTP_200_OK)


class CheckMailItemAPIView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")
        barcode = request.data.get("barcode")
        checked_image_base64 = request.data.get("checked_image")  # base64 rasm

        if not phone_number or not barcode:
            return Response({"detail": "phone_number va barcode talab qilinadi."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = BankUsers.objects.get(phone_number=phone_number)
        except BankUsers.DoesNotExist:
            return Response({"detail": "Noto‘g‘ri token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            mail_item = MailItem.objects.get(barcode=barcode)
        except MailItem.DoesNotExist:
            return Response({"detail": "Bunday barcode topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        mail_item.is_check = True
        mail_item.checked_name = user.fish
        mail_item.checked_time = timezone.now()

        if checked_image_base64:
            try:
                format, imgstr = checked_image_base64.split(';base64,')  # data:image/png;base64,xxxx
                ext = format.split('/')[-1]
                file_name = f"{uuid.uuid4()}.{ext}"
                mail_item.checked_image = ContentFile(base64.b64decode(imgstr), name=file_name)
            except Exception as e:
                return Response({"detail": "Rasmni saqlashda xatolik yuz berdi.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        mail_item.save()

        return Response({"detail": "MailItem muvaffaqiyatli tekshirildi."}, status=status.HTTP_200_OK)
    
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = TokenObtainPairSerializer


class MailItemUpdateStatus(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        print(data)
        barcode = data.get("order_number")
        warehouse_name = data.get("warehouse_name")
        status_text = data.get("status")
        date_value = data.get("date")

        if not barcode:
            return Response({"error": "order_number (barcode) is required"}, status=400)

        if isinstance(date_value, str):
            event_date = parse_datetime(date_value)
        else:
            return Response({"error": "Invalid or missing 'date' field"}, status=400)

        try:
            mail_item = MailItem.objects.get(barcode=barcode)
        except MailItem.DoesNotExist:
            mail_item = MailItem(barcode=barcode)

        # Har doim statusga bog'liq bo'lmasdan region/districtni yangilaymiz
        found_location = False
        try:
            district = District.objects.get(name__icontains=warehouse_name)
            mail_item.district = district.name
            mail_item.region = district.region.name
            found_location = True
        except District.DoesNotExist:
            try:
                region = Region.objects.get(name__icontains=warehouse_name)
                mail_item.region = region.name
                found_location = True
            except Region.DoesNotExist:
                pass  # Hech narsa o‘zgartirilmaydi

        if status_text == "completed":
            mail_item.is_delivered = True

        elif status_text == "received":
            mail_item.received_date = event_date

        # Umumiy maydonlar
        mail_item.last_event_date = event_date

        if not isinstance(mail_item.last_event_name, list):
            mail_item.last_event_name = []
        mail_item.last_event_name.append(status_text)

        mail_item.save()

        return Response({
            "message": "MailItem updated or created successfully",
            "region": mail_item.region,
            "district": mail_item.district
        }, status=200)
from django.shortcuts import render
from .serializers import TokenObtainPairSerializer,BankUsersProfileSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
import threading
from django.db.models import Sum, Count
from rest_framework import status
from .models import MailItem
import cv2
import numpy as np
from PIL import Image
from .models import BankUsers
from django.db.models.functions import TruncMonth
import calendar
from django.db.models import Count
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import ListAPIView
from .serializers import MailItemSerializer
from collections import Counter
from django.db.models import Q

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


class MailItemPagination(PageNumberPagination):
    page_size = 10  # Har bir sahifada 10 ta element chiqadi
    page_size_query_param = 'page_size'
    max_page_size = 100



class MailItemAllListView(APIView):
    permission_classes = [IsAuthenticated]  # Bu API uchun autentifikatsiya talab qilinadi

    def get(self, request):
        # Query parametrlardan filter uchun imkoniyat yaratish
        filters = Q()

        # Barcha mumkin bo‘lgan filter parametrlari
        batch = request.GET.get('batch')
        if batch:
            filters &= Q(batch__icontains=batch)  # Batch bo‘yicha filter

        barcode = request.GET.get('barcode')
        if barcode:
            filters &= Q(barcode__icontains=barcode)  # Barcode bo‘yicha filter

        weight = request.GET.get('weight')
        if weight:
            try:
                weight = float(weight)
                filters &= Q(weight=weight)  # Weight bo‘yicha filter
            except ValueError:
                return Response({"error": "Invalid weight parameter"}, status=400)

        city = request.GET.get('city')
        if city:
            filters &= Q(city__icontains=city)  # City bo‘yicha filter

        # Last event name (listning oxirgi elementi bo‘yicha filter)
        

        date_fields = ['send_date', 'received_date', 'last_event_date']
        for field in date_fields:
            date_value = request.GET.get(field)
            if date_value:
                filters &= Q(**{f"{field}": date_value})  # Aniq sana bo‘yicha filter

            from_date = request.GET.get(f"{field}_from")
            if from_date:
                filters &= Q(**{f"{field}__gte": from_date})  # Sana oraliq boshlanishi

            to_date = request.GET.get(f"{field}_to")
            if to_date:
                filters &= Q(**{f"{field}__lte": to_date})  # Sana oraliq tugashi

        # MailItem modelini filtratsiya qilish
        mail_items = MailItem.objects.filter(filters).order_by('-updated_at')
        last_event_name = request.GET.get('last_event_name')
        if last_event_name:
            mail_items = [item for item in mail_items if item.last_event_name and item.last_event_name[-1] == last_event_name]
        # Sahifalashni qo‘shish
        paginator = MailItemPagination()  # Pagination obyektini yaratish
        paginated_mail_items = paginator.paginate_queryset(mail_items, request)  # Querysetni sahifalash
        
        # Serializer orqali ma'lumotlarni qaytarish
        serializer = MailItemSerializer(paginated_mail_items, many=True)
        
        # Sahifalangan javobni qaytarish
        return paginator.get_paginated_response(serializer.data)
    


class DeliveredMailItemListView(ListAPIView):
    serializer_class = MailItemSerializer
    pagination_class = MailItemPagination

    def get_queryset(self):
        return MailItem.objects.filter(is_delivered=True).order_by('-send_date')


class MailItemStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Agar ochiq bo'lishini istasangiz: [AllowAny]

    def get(self, request):
        total = MailItem.objects.count()
        
        completed = MailItem.objects.filter(
    last_event_name__contains=["completed"]
).count()

        return_status = MailItem.objects.filter(
    last_event_name__contains=["returning_to_origin"]
).count()

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
            "other_items": {
                "count": other_count,
                "percent": f"{percentage(other_count)}%"
            },
             "return": {
                "count": return_status,
                "percent": f"{percentage(return_status)}%"
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
        token = request.data.get("token")
        barcode = request.data.get("barcode")

        if not token or not barcode:
            return Response({"detail": "Token va barcode talab qilinadi."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = BankUsers.objects.get(token=token)
        except BankUsers.DoesNotExist:
            return Response({"detail": "Noto‘g‘ri token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            mail_item = MailItem.objects.get(barcode=barcode)
        except MailItem.DoesNotExist:
            return Response({"detail": "Bunday barcode topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        mail_item.is_check = True
        mail_item.checked_name = user.fish
        mail_item.save()

        return Response({"detail": "MailItem muvaffaqiyatli tekshirildi."}, status=status.HTTP_200_OK)



class FaceRecognitionAPIView(APIView):
    def post(self, request):
        uploaded_file = request.FILES.get('photo')
        if not uploaded_file:
            return Response({'error': 'Rasm jo‘natilmagan'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Yuborilgan rasmni ochish va OpenCV formatiga o‘tkazish
            img = Image.open(uploaded_file)
            img = np.array(img)
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

            # Haar Cascade yordamida yuzni aniqlash
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            if len(faces) == 0:
                return Response({'error': 'Yuz topilmadi'}, status=status.HTTP_400_BAD_REQUEST)

            # Rasmni faqat birinchi yuz uchun o‘zgartirish
            x, y, w, h = faces[0]
            face_img = gray[y:y+h, x:x+w]

            # Rasmning xususiyatlarini olish
            uploaded_encoding = cv2.resize(face_img, (128, 128))  # Yuzni kichraytirish va moslashtirish

            # Barcha foydalanuvchilarning rasmlarini tekshirish
            for profile in BankUsers.objects.all():
                if not profile.photo:
                    continue
                try:
                    # Foydalanuvchining rasmidan yuzni aniqlash
                    existing_image = Image.open(profile.photo.path)
                    existing_image = np.array(existing_image)
                    existing_gray = cv2.cvtColor(existing_image, cv2.COLOR_RGB2GRAY)

                    existing_faces = face_cascade.detectMultiScale(existing_gray, 1.1, 4)
                    if len(existing_faces) == 0:
                        continue

                    # Rasmni faqat birinchi yuz uchun o‘zgartirish
                    ex_x, ex_y, ex_w, ex_h = existing_faces[0]
                    existing_face_img = existing_gray[ex_y:ex_y+ex_h, ex_x:ex_x+ex_w]
                    existing_encoding = cv2.resize(existing_face_img, (128, 128))  # Yuzni kichraytirish va moslashtirish

                    # Yuzlarni solishtirish
                    if np.array_equal(uploaded_encoding, existing_encoding):
                        # Agar yuzlar mos kelsa, faqat foydalanuvchining tokenini qaytarish
                        return Response({'token': profile.token}, status=status.HTTP_200_OK)

                except Exception as e:
                    continue

            # Agar mos foydalanuvchi topilmasa
            return Response({'message': 'Mos foydalanuvchi topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



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
        if isinstance(date_value, str):
            event_date = parse_datetime(date_value)
        else:
            return Response({"error": "Invalid or missing 'date' field"}, status=400) 

        try:
            mail_item = MailItem.objects.get(barcode=barcode)
            if status_text == "completed":
                mail_item.city = warehouse_name
                mail_item.last_event_name.append(status_text)
                mail_item.last_event_date = event_date
                mail_item.is_delivered = True 
                mail_item.save(update_fields=['city', 'last_event_name', 'last_event_date','updated_at','is_delivered'])
            elif status_text == "completed":
                mail_item.city = warehouse_name
                mail_item.last_event_name.append(status_text)
                mail_item.last_event_date = event_date
                mail_item.received_date = event_date
                mail_item.save(update_fields=['city', 'last_event_name', 'last_event_date','updated_at','received_date'])
            else:
                mail_item.city = warehouse_name
                mail_item.last_event_name.append(status_text)
                mail_item.last_event_date = event_date 
                mail_item.save(update_fields=['city', 'last_event_name', 'last_event_date','updated_at'])


            return Response({"message": "MailItem updated successfully"}, status=200)


        except MailItem.DoesNotExist:
            return Response({"error": f"MailItem with barcode {barcode} not found"}, status=status.HTTP_404_NOT_FOUND)



from django.shortcuts import render
from .serizalizers import TokenObtainPairSerializer,BankUsersProfileSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
import threading
from rest_framework import status
from .models import MailItem
import cv2
import numpy as np
from PIL import Image
from .models import BankUsers


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
            else:
                mail_item.city = warehouse_name
                mail_item.last_event_name.append(status_text)
                mail_item.last_event_date = event_date 
                mail_item.save(update_fields=['city', 'last_event_name', 'last_event_date','updated_at'])


            return Response({"message": "MailItem updated successfully"}, status=200)


        except MailItem.DoesNotExist:
            return Response({"error": f"MailItem with barcode {barcode} not found"}, status=status.HTTP_404_NOT_FOUND)




from django.contrib import admin
from .models import MailItem, CustomUser,BankUsers
from django.contrib.auth.admin import UserAdmin

class BankUsersAdmin(admin.ModelAdmin):
    list_display = ('fish', 'phone_number', 'region', 'district', 'lavozimi', 'token')
    search_fields = ('fish', 'phone_number', 'region', 'district', 'lavozimi')
    list_filter = ('region', 'district', 'lavozimi')
    ordering = ('fish',)
    readonly_fields = ('token',)  # Token faqat o'qilishi mumkin

admin.site.register(BankUsers, BankUsersAdmin)

class CustomUserAdmin(admin.ModelAdmin):
    # 'created_at' maydonini faqat ko'rsatish uchun readonly qilish
    readonly_fields = ('created_at',)
    
    # Maydonlarni chiqarish tartibini belgilash
    fieldsets = (
        (None, {
            'fields': ('phone_number', 'first_name', 'last_name', 'password', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Additional Info', {
            'fields': ('created_at',),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)
@admin.register(MailItem)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("barcode", "batch", "last_event_name")  # Jadvaldagi ustunlar
    list_filter = ("barcode","batch", "last_event_name")  # Filtr bo‘limi
    search_fields = ("barcode","batch", "last_event_name")  # Qidirish imkoniyati

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from django import forms
from django.template.response import TemplateResponse
import xml.etree.ElementTree as ET
from django.utils.dateparse import parse_datetime

class XMLUploadForm(forms.Form):
    xml_file = forms.FileField()

class MailItemAdmin(admin.ModelAdmin):
    list_display = ("barcode", "batch", "weight", "send_date", "last_event_name")
    change_list_template = "admin/mailitem_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("upload-xml/", self.admin_site.admin_view(self.upload_xml), name="upload-xml"),
        ]
        return custom_urls + urls

    def upload_xml(self, request):
        if request.method == "POST":
            form = XMLUploadForm(request.POST, request.FILES)
            if form.is_valid():
                xml_file = request.FILES["xml_file"]
                xml_data = xml_file.read().decode("utf-8")

                tree = ET.ElementTree(ET.fromstring(xml_data))
                root = tree.getroot()
                namespaces = {'ips': 'http://upu.int/ips'}  

                mail_items = root.findall(".//ips:MailItem", namespaces)
                created_count = 0
                error_messages = []

                for item in mail_items:
                    barcode = item.get("ItemId")  

                    if MailItem.objects.filter(barcode=barcode).exists():
                        error_messages.append(f"Barcode {barcode} already exists!")
                        continue

                    batch_element = item.find("ips:Misc1", namespaces)
                    batch = batch_element.text if batch_element is not None else None

                    weight_element = item.find("ips:ItemWeight", namespaces)
                    weight = float(weight_element.text) if weight_element is not None else 0.0

                    send_date_element = item.find("ips:ItemEvent/ips:Date", namespaces)
                    send_date = parse_datetime(send_date_element.text) if send_date_element is not None else None

                    first_status_element = item.find("ips:ItemEvent/ips:TNCd", namespaces)
                    first_status = first_status_element.text if first_status_element is not None else None
                    last_event_name = ["On way"] if first_status == "1261" else []

                    MailItem.objects.create(
                        barcode=barcode,
                        batch=batch,
                        weight=weight,
                        send_date=send_date,
                        last_event_name=last_event_name
                    )
                    created_count += 1

                if error_messages:
                    return TemplateResponse(request, "admin/xml_upload_result.html", {
                        "errors": error_messages,
                        "created_count": created_count,
                    })
                return redirect("..")

        form = XMLUploadForm()
        return TemplateResponse(request, "admin/xml_upload.html", {"form": form})
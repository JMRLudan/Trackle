from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from .models import User, Subject, Requirement, Student

# Register your models here.
admin.site.register(User)
admin.site.register(Subject)
admin.site.register(Requirement)
admin.site.register(Student)

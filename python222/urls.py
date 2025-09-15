
# from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve

from python222 import settings

urlpatterns = [

    # path('admin/', admin.site.urls),
    path('user/', include('user.urls')), # 用户模块
    # path('role/', include('role.urls')), # 角色模块
    # path('menu/', include('menu.urls')), # 权限模块
    re_path('media/(?P<path>.*)', serve, {'document_root': settings.MEDIA_ROOT},name='media')
]


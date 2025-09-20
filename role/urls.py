from django.urls import path

from role.views import SearchView

urlpatterns = [
    path('search/', SearchView.as_view()), # 角色信息查询
]
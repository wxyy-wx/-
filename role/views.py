from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django.core.paginator import Paginator
import json
from .models import SysRole

# Create your views here.


# 角色信息查询
class SearchView(View):
    def post(self, request):
        data = json.loads(request.body.decode("utf-8"))
        pageNum = data['pageNum'] # 当前页
        pageSize = data['pageSize'] # 每页大小
        query = data['query'] # 查询参数
        print(pageSize, pageNum)
        roleListPage = Paginator(SysRole.objects.filter(name__icontains=query),
        pageSize).page(pageNum)
        obj_roles = roleListPage.object_list.values() # 转成字典
        roles = list(obj_roles) # 把外层的容器转为List
        total = SysRole.objects.filter(name__icontains=query).count()
        return JsonResponse(
            {'code': 200, 'roleList': roles, 'total': total})
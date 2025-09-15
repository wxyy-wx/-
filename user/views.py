import json
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password, make_password
# 导入角色、菜单模型（跨应用关联，适配当前权限菜单逻辑）
from role.models import SysRole
from menu.models import SysMenu
# 导入菜单序列化器（用于菜单数据格式处理）
from menu.serializers import SysMenuSerializer
from .models import SysUser


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(View):
    def buildTreeMenu(self, sysMenuList):
        resultMenuList = []
        if not sysMenuList:
            return resultMenuList
        for menu in sysMenuList:
            for sub_menu in sysMenuList:
                if sub_menu.parent_id == menu.id:
                    if not hasattr(menu, "children"):
                        menu.children = []
                    menu.children.append(sub_menu)
            if menu.parent_id == 0:
                resultMenuList.append(menu)
        return resultMenuList

    def post(self, request):
        username = request.GET.get('username', '')
        password = request.GET.get('password', '')
        request.GET.get('rememberMe', False)

        if not username or not password:
            try:
                data = json.loads(request.body)
                username = data.get('username', '')
                password = data.get('password', '')
            except json.JSONDecodeError:
                return JsonResponse({'code': 400, 'info': '请求格式错误，请用JSON或URL参数'})

        try:
            user = SysUser.objects.get(username=username)
            if password and check_password(password, user.password):
                roleList = SysRole.objects.raw("""
                    SELECT id FROM sys_role 
                    WHERE id IN (SELECT role_id FROM sys_user_role WHERE user_id=%s)
                """, [user.id])
                roleIds = [role.id for role in roleList]

                menuSet = set()
                if roleIds:
                    for roleId in roleIds:
                        menus = SysMenu.objects.raw("""
                            SELECT * FROM sys_menu 
                            WHERE id IN (SELECT menu_id FROM sys_role_menu WHERE role_id=%s)
                        """, [roleId])
                        for menu in menus:
                            menuSet.add(menu)
                menuList = list(menuSet)

                sortedMenus = sorted(menuList, key=lambda x: x.order_num if x.order_num else 999)
                treeMenus = self.buildTreeMenu(sortedMenus)
                serializerMenus = [SysMenuSerializer(menu).data for menu in treeMenus]

                # -------------------------- 关键修改开始 --------------------------
                # 1. 生成Token（原有逻辑）
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)

                # 2. 新增：构建userInfo（包含用户名、头像路径，适配前端currentUser存储）
                user_info = {
                    'username': user.username,  # 前端显示用户名需此字段
                    # 若SysUser模型未添加avatar字段，需先添加（下方有模型字段定义提示）
                    'avatar': user.avatar if hasattr(user, 'avatar') and user.avatar else ''
                }

                # 3. 响应中新增userInfo字段（前端需通过data.userInfo读取）
                return JsonResponse({
                    'code': 200,
                    'token': access_token,
                    'menuList': serializerMenus,
                    'userInfo': user_info,  # 新增：为前端提供用户信息
                    'info': '登录成功！'
                })
                # -------------------------- 关键修改结束 --------------------------
            else:
                print("密码验证失败！")
                return JsonResponse({'code': 401, 'info': '密码错误！'})
        except SysUser.DoesNotExist:
            return JsonResponse({'code': 401, 'info': '用户名不存在！'})
        except Exception as e:
            print(f"登录异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误！'})

class TestView(View):
    def get(self, request):
        # 兼容Bearer Token格式
        token = request.META.get('HTTP_AUTHORIZATION', '')
        if token.startswith('Bearer '):
            token = token.split(' ')[1]

        if token:
            try:
                userList = list(SysUser.objects.all().values())
                return JsonResponse({'code': 200, 'info': '测试！', 'data': userList})
            except Exception as e:
                print(f"测试接口异常：{str(e)}")
                return JsonResponse({'code': 500, 'info': '测试接口查询失败！'})
        else:
            return JsonResponse({'code': 401, 'info': '没有访问权限，请先登录！'})


class JwtTestView(View):
    def get(self, request):
        try:
            # 测试用户创建（密码哈希存储）
            user, created = SysUser.objects.get_or_create(
                username='python222',
                defaults={'password': make_password('123456')}
            )
            # 生成Token
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            return JsonResponse({
                'code': 200,
                'token': access_token,
                'refresh_token': str(refresh),
                'info': '测试Token生成成功！'
            })
        except Exception as e:
            print(f"Jwt测试异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '测试接口异常！'})
import json

from django.core.paginator import Paginator
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password, make_password

from python222 import settings
# 导入角色、菜单模型（跨应用关联，适配当前权限菜单逻辑）
from role.models import SysRole, SysUserRole
from menu.models import SysMenu
# 导入菜单序列化器（用于菜单数据格式处理）
from menu.serializers import SysMenuSerializer
from .models import SysUser, SysUserSerializer
from datetime import datetime  # 新增：导入datetime模块，对应文档1-604行日期处理逻辑
from django.contrib.auth.hashers import make_password  # 新增：导入密码哈希工具，对应文档1-604行安全规范



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

                roles = ",".join([role.name for role in roleList])

                # 1. 生成Token（原有逻辑）
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)

                # 2. 新增：构建userInfo（包含用户名、头像路径，适配前端currentUser存储）
                user_info = {
                    'username': user.username,  # 前端显示用户名需此字段
                    # 若SysUser模型未添加avatar字段，需先添加（下方有模型字段定义提示）
                    'avatar': user.avatar if hasattr(user, 'avatar') and user.avatar else '',
                    'create_time': user.create_time.strftime('%Y-%m-%d %H:%M:%S') if user.create_time else None,
                }

                # 3. 响应中新增userInfo字段（前端需通过data.userInfo读取）
                return JsonResponse({
                    'code': 200,
                    'token': access_token,
                    'menuList': serializerMenus,
                    'userInfo': {  # 原有userInfo字段不变
                        'username': user.username,
                        'id': user.id,
                        'avatar': user.avatar if hasattr(user, 'avatar') and user.avatar else '',
                        "create_time": user.create_time.strftime('%Y-%m-%d %H:%M:%S') if user.create_time else None,
                    },  # 新增：为前端提供用户信息
                    'roles': roles,
                    'info': '登录成功！',
                    'id': user.id,
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


@method_decorator(csrf_exempt, name='dispatch')  # 对齐文档3-299行csrf豁免规范
class SaveView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))
            print(f"Received data: {data}")

            if data['id'] == -1:  # 添加用户（对齐文档3-604行添加逻辑）
                # 1. 用户名唯一性校验（文档隐含的基础校验）
                if SysUser.objects.filter(username=data['username']).exists():
                    return JsonResponse({'code': 400, 'info': f'用户名"{data["username"]}"已存在，请更换！'})

                # 2. 创建用户（严格对齐文档3-604行字段赋值）
                obj_sysUser = SysUser(
                    username=data['username'],
                    # 文档3-604行默认密码123456，且强制哈希存储
                    password=make_password(data.get('password', '123456')),
                    # 文档3-604行默认头像default.jpg
                    avatar=data.get('avatar', 'default.jpg'),
                    email=data.get('email', ''),
                    phonenumber=data.get('phonenumber', ''),
                    login_date=None,  # 新用户无登录时间（文档隐含逻辑）
                    status=data.get('status', 1),  # 文档3-48行status默认1（正常）
                    # 修复datetime调用错误：datetime.datetime.now()而非datetime.now()
                    create_time=datetime.datetime.now().date(),  # 对齐文档3-604行创建时间赋值
                    update_time=datetime.datetime.now().date(),  # 新增时同步更新时间
                    remark=data.get('remark', '')
                )
                obj_sysUser.save()
                print(f"User {data['username']} created successfully.")

            else:  # 修改用户（对齐文档3-604行修改逻辑）
                try:
                    # 1. 获取已有用户（文档3-604行通过id查询）
                    existing_user = SysUser.objects.get(id=data['id'])
                    print(f"Found user with id {data['id']}: {existing_user.username}")
                except SysUser.DoesNotExist:
                    return JsonResponse({'code': 404, 'info': '用户不存在！'})

                # 2. 用户名变更校验（文档隐含的唯一性逻辑）
                if data['username'] != existing_user.username:
                    if SysUser.objects.filter(username=data['username']).exists():
                        return JsonResponse({'code': 400, 'info': f'用户名"{data["username"]}"已存在，请更换！'})

                # 3. 基础字段更新（对齐文档3-604行字段覆盖逻辑）
                existing_user.username = data['username']
                existing_user.avatar = data.get('avatar', existing_user.avatar)
                existing_user.email = data.get('email', existing_user.email)
                existing_user.phonenumber = data.get('phonenumber', existing_user.phonenumber)
                existing_user.login_date = data.get('login_date', existing_user.login_date)
                existing_user.status = data.get('status', existing_user.status)
                existing_user.remark = data.get('remark', existing_user.remark)

                # 4. 密码特殊处理（文档3-604行未显式处理，按安全规范补充哈希）
                if 'password' in data and data['password']:
                    existing_user.password = make_password(data['password'])

                # 5. 更新时间（对齐文档3-604行update_time赋值）
                # 修复datetime调用错误：datetime.datetime.now()而非datetime.now()
                existing_user.update_time = datetime.datetime.now().date()

                existing_user.save()
                print(f"User {existing_user.username} updated successfully.")

            # 统一响应格式（对齐文档3-604行返回规范）
            return JsonResponse({'code': 200, 'info': '用户信息保存成功！'})

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return JsonResponse({'code': 400, 'info': '请求格式错误，需为JSON'})
        except Exception as e:
            print(f"保存用户异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误！'})


@method_decorator(csrf_exempt, name='dispatch')
class PwdView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))
            user_id = data.get('id')
            old_password = data.get('oldPassword')
            new_password = data.get('newPassword')

            if not all([user_id, old_password, new_password]):
                return JsonResponse({'code': 400, 'info': '参数不完整，请检查'})

            try:
                user = SysUser.objects.get(id=user_id)
            except SysUser.DoesNotExist:
                return JsonResponse({'code': 404, 'info': '用户不存在'})

            # 验证旧密码（假设数据库中密码是加密存储的）
            if not check_password(old_password, user.password):
                return JsonResponse({'code': 500, 'info': '原密码错误！'})

            # 加密新密码并更新
            user.password = make_password(new_password)
            user.update_time = datetime.now().date()
            user.save()

            return JsonResponse({'code': 200, 'info': '密码修改成功'})
        except json.JSONDecodeError:
            return JsonResponse({'code': 400, 'info': '请求格式错误，需为JSON'})
        except Exception as e:
            print(f"修改密码异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误'})



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
        id=request.GET.get('id', '')
        request.GET.get('rememberMe', False)

        if not username or not password:
            try:
                data = json.loads(request.body)
                username = data.get('username', '')
                password = data.get('password', '')
                id=data.get('id', '')
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

                roles = ",".join([role.name for role in roleList])

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
                    'userInfo': {  # 原有userInfo字段不变
                        'username': user.username,
                        'id': user.id,
                        'avatar': user.avatar if hasattr(user, 'avatar') and user.avatar else '',
                        'phonenumber': user.phonenumber if hasattr(user, 'phonenumber') else '',
                        'email': user.email if hasattr(user, 'email') else ''

                    },  # 新增：为前端提供用户信息
                    'roles': roles,
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


@method_decorator(csrf_exempt, name='dispatch')  # 对齐文档3-299行csrf豁免规范
class SaveView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))
            print(f"Received data: {data}")

            if data['id'] == -1:  # 添加用户（对齐文档3-604行添加逻辑）
                # 1. 用户名唯一性校验（文档隐含的基础校验）
                if SysUser.objects.filter(username=data['username']).exists():
                    return JsonResponse({'code': 400, 'info': f'用户名"{data["username"]}"已存在，请更换！'})

                # 2. 创建用户（严格对齐文档3-604行字段赋值）
                obj_sysUser = SysUser(
                    username=data['username'],
                    # 文档3-604行默认密码123456，且强制哈希存储
                    password=make_password(data.get('password', '123456')),
                    # 文档3-604行默认头像default.jpg
                    avatar=data.get('avatar', 'default.jpg'),
                    email=data.get('email', ''),
                    phonenumber=data.get('phonenumber', ''),
                    login_date=None,  # 新用户无登录时间（文档隐含逻辑）
                    status=data.get('status', 1),  # 文档3-48行status默认1（正常）
                    create_time=datetime.now().date(),  # 对齐文档3-604行创建时间赋值
                    update_time=datetime.now().date(),  # 新增时同步更新时间
                    remark=data.get('remark', '')
                )
                obj_sysUser.save()
                print(f"User {data['username']} created successfully.")

            else:  # 修改用户（对齐文档3-604行修改逻辑）
                try:
                    # 1. 获取已有用户（文档3-604行通过id查询）
                    existing_user = SysUser.objects.get(id=data['id'])
                    print(f"Found user with id {data['id']}: {existing_user.username}")
                except SysUser.DoesNotExist:
                    return JsonResponse({'code': 404, 'info': '用户不存在！'})

                # 2. 用户名变更校验（文档隐含的唯一性逻辑）
                if data['username'] != existing_user.username:
                    if SysUser.objects.filter(username=data['username']).exists():
                        return JsonResponse({'code': 400, 'info': f'用户名"{data["username"]}"已存在，请更换！'})

                # 3. 基础字段更新（对齐文档3-604行字段覆盖逻辑）
                existing_user.username = data['username']
                existing_user.avatar = data.get('avatar', existing_user.avatar)
                existing_user.email = data.get('email', existing_user.email)
                existing_user.phonenumber = data.get('phonenumber', existing_user.phonenumber)
                existing_user.login_date = data.get('login_date', existing_user.login_date)
                existing_user.status = data.get('status', existing_user.status)
                existing_user.remark = data.get('remark', existing_user.remark)

                # 4. 密码特殊处理（文档3-604行未显式处理，按安全规范补充哈希）
                if 'password' in data and data['password']:
                    existing_user.password = make_password(data['password'])

                # 5. 更新时间（对齐文档3-604行update_time赋值）
                existing_user.update_time = datetime.now().date()

                existing_user.save()
                print(f"User {existing_user.username} updated successfully.")

            # 统一响应格式（对齐文档3-604行返回规范）
            return JsonResponse({'code': 200, 'info': '用户信息保存成功！'})

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return JsonResponse({'code': 400, 'info': '请求格式错误，需为JSON'})
        except Exception as e:
            print(f"保存用户异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误！'})


@method_decorator(csrf_exempt, name='dispatch')  # 对齐文档3-299行CSRF豁免
class ActionView(View):
    def get(self, request):
        """
        根据id获取用户信息（对齐文档3-606行ActionView逻辑）
        :param request:
        :return:
        """
        try:
            id = request.GET.get("id")
            # 处理"id为空"和"用户不存在"异常（文档3-314行异常处理规范）
            if not id:
                return JsonResponse({'code': 400, 'info': '参数id不能为空！'})

            user_object = SysUser.objects.get(id=id)
            # 用序列化器返回数据（文档3-325行序列化器使用规范）
            return JsonResponse({
                'code': 200,
                'user': SysUserSerializer(user_object).data,
                'info': '获取用户信息成功！'
            })
        except SysUser.DoesNotExist:
            return JsonResponse({'code': 404, 'info': '用户不存在！'})
        except Exception as e:
            print(f"获取用户异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误！'})

    def delete(self, request):
        """
        删除操作
        :param request:
        :return:
        """

        idList = json.loads(request.body.decode("utf-8"))
        SysUserRole.objects.filter(user_id__in=idList).delete()
        SysUser.objects.filter(id__in=idList).delete()
        return JsonResponse({'code': 200})


@method_decorator(csrf_exempt, name='dispatch')  # 前端POST需豁免CSRF
class CheckView(View):
    def post(self, request):
        """验证用户名是否重复（对齐文档3-608行CheckView逻辑）"""
        try:
            data = json.loads(request.body.decode("utf-8"))
            username = data.get('username', '')  # 用get避免KeyError
            print("username=", username)

            if not username:
                return JsonResponse({'code': 400, 'info': '用户名不能为空！'})

            # 用户名唯一性校验（文档3-608行核心逻辑）
            if SysUser.objects.filter(username=username).exists():
                return JsonResponse({'code': 500, 'info': '用户名已存在，请更换！'})
            else:
                return JsonResponse({'code': 200, 'info': '用户名可用！'})
        except json.JSONDecodeError:
            return JsonResponse({'code': 400, 'info': '请求格式错误，需为JSON！'})
        except Exception as e:
            print(f"校验用户名异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误！'})

@method_decorator(csrf_exempt, name='dispatch')
class PwdView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))
            user_id = data.get('id')
            old_password = data.get('oldPassword')
            new_password = data.get('newPassword')

            if not all([user_id, old_password, new_password]):
                return JsonResponse({'code': 400, 'info': '参数不完整，请检查'})

            try:
                user = SysUser.objects.get(id=user_id)
            except SysUser.DoesNotExist:
                return JsonResponse({'code': 404, 'info': '用户不存在'})

            # 验证旧密码（假设数据库中密码是加密存储的）
            if not check_password(old_password, user.password):
                return JsonResponse({'code': 500, 'info': '原密码错误！'})

            # 加密新密码并更新
            user.password = make_password(new_password)
            user.update_time = datetime.now().date()
            user.save()

            return JsonResponse({'code': 200, 'info': '密码修改成功'})
        except json.JSONDecodeError:
            return JsonResponse({'code': 400, 'info': '请求格式错误，需为JSON'})
        except Exception as e:
            print(f"修改密码异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误'})


@method_decorator(csrf_exempt, name='dispatch')
class ImageView(View):
    def post(self, request):
        file = request.FILES.get('avatar')
        print("接收到的文件:", file)
        if file:
            file_name = file.name
            suffix_name = file_name[file_name.rfind("."):]
            new_file_name = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + suffix_name
            file_path = f"{settings.MEDIA_ROOT}/userAvatar/{new_file_name}"
            print("文件存储路径:", file_path)
            try:
                with open(file_path, 'wb') as f:
                    for chunk in file.chunks():
                        f.write(chunk)
                return JsonResponse({'code': 200, 'title': new_file_name})
            except Exception as e:
                print(f"上传头像异常: {e}")
                return JsonResponse({'code': 500, 'errorInfo': '上传头像失败'})
        return JsonResponse({'code': 400, 'errorInfo': '未获取到上传的头像文件'})

@method_decorator(csrf_exempt, name='dispatch')
class AvatarView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))
            print("AvatarView接收到的数据data:", data)
            user_id = data.get('id')
            avatar = data.get('avatar')
            print("user_id:", user_id, "avatar:", avatar)
            if not user_id or not avatar:
                return JsonResponse({'code': 400, 'errorInfo': 'id和avatar参数缺失'})
            obj_user = SysUser.objects.get(id=user_id)
            obj_user.avatar = avatar
            obj_user.save()
            return JsonResponse({'code': 200, 'info': '头像更新成功'})
        except SysUser.DoesNotExist:
            return JsonResponse({'code': 404, 'errorInfo': '用户不存在'})
        except Exception as e:
            print(f"更新头像异常: {e}")
            return JsonResponse({'code': 500, 'errorInfo': '服务器内部错误'})


@method_decorator(csrf_exempt, name='dispatch')  # CSRF豁免，适配前端POST/GET请求
class PasswordView(View):
    def get(self, request):
        """重置用户密码为默认123456（需哈希存储）"""
        try:
            user_id = request.GET.get("id")
            if not user_id:
                return JsonResponse({'code': 400, 'info': '参数id不能为空'})

            user = SysUser.objects.get(id=user_id)
            # 密码必须哈希存储（对齐文档安全规范，参考SaveView实现）
            user.password = make_password('123456')
            user.update_time = datetime.now().date()
            user.save()
            return JsonResponse({'code': 200, 'info': '密码重置成功，默认密码：123456'})

        except SysUser.DoesNotExist:
            return JsonResponse({'code': 404, 'info': '用户不存在'})
        except Exception as e:
            print(f"重置密码异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误'})


@method_decorator(csrf_exempt, name='dispatch')  # CSRF豁免，适配前端POST请求
class StatusView(View):
    def post(self, request):
        """修改用户状态（启用/禁用）"""
        try:
            data = json.loads(request.body.decode("utf-8"))
            user_id = data.get('id')
            status = data.get('status')

            if not all([user_id, status is not None]):  # status可能为0（禁用），需显式判断非None
                return JsonResponse({'code': 400, 'info': '参数id和status不能为空'})

            user = SysUser.objects.get(id=user_id)
            user.status = status
            user.update_time = datetime.now().date()  # 更新状态时同步更新时间
            user.save()
            return JsonResponse({'code': 200, 'info': '用户状态更新成功'})

        except json.JSONDecodeError:
            return JsonResponse({'code': 400, 'info': '请求格式错误，需为JSON'})
        except SysUser.DoesNotExist:
            return JsonResponse({'code': 404, 'info': '用户不存在'})
        except Exception as e:
            print(f"修改状态异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误'})









# 用户信息查询
@method_decorator(csrf_exempt, name='dispatch')  # 对齐文档3-299行csrf豁免规范
class SearchView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))
            pageNum = data['pageNum']  # 当前页（对应文档3-581行分页参数）
            pageSize = data['pageSize']  # 每页大小（对应文档3-581行分页参数）
            query = data.get('query', '')  # 查询参数，默认空字符串避免KeyError

            # 1. 修复查询语法：用__icontains实现不区分大小写模糊查询（对齐文档3-594行）
            # 2. 修复SQL注入：raw查询用参数化传递userId（对齐文档3-394行安全规范）
            user_queryset = SysUser.objects.filter(username__icontains=query)
            userListPage = Paginator(user_queryset, pageSize).page(pageNum)

            obj_users = userListPage.object_list.values()  # 转字典（对应文档3-68行序列化处理）
            users = list(obj_users)

            for user in users:
                userId = user['id']
                # 修复SQL拼接风险：用参数化查询传递userId
                roleList = SysRole.objects.raw("""
                    SELECT id, name FROM sys_role 
                    WHERE id IN (SELECT role_id FROM sys_user_role WHERE user_id = %s)
                """, [userId])  # 对齐文档3-394行raw查询语法

                roleListDict = []
                for role in roleList:
                    roleDict = {'id': role.id, 'name': role.name}
                    roleListDict.append(roleDict)
                user['roleList'] = roleListDict  # 为用户添加角色列表（对应文档3-594行角色关联逻辑）

            total = user_queryset.count()  # 优化计数：直接用查询集计数，避免重复查询
            return JsonResponse({'code': 200, 'userList': users, 'total': total})

        except json.JSONDecodeError:
            return JsonResponse({'code': 400, 'info': '请求格式错误，需为JSON'})  # 对齐文档3-525行异常处理
        except Exception as e:
            print(f"查询用户异常：{str(e)}")
            return JsonResponse({'code': 500, 'info': '服务器内部错误'})  # 对齐文档3-314行异常捕获


# @method_decorator(csrf_exempt, name='dispatch')
# class AssignRolesView(View):
#     def post(self, request):
#         try:
#             data = request.POST  # 假设前端传递form-data格式数据，若为json需用json.loads(request.body)
#             user_id = data.get('userId')
#             role_ids = data.getlist('roleIds[]')  # 若前端传递的是数组形式的角色ID列表
#
#             if not user_id or not role_ids:
#                 return JsonResponse({'code': 400, 'info': '用户ID和角色ID不能为空'})
#
#             # 先删除该用户已有的角色关联
#             SysUserRole.objects.filter(user_id=user_id).delete()
#             # 再添加新的角色关联
#             for role_id in role_ids:
#                 SysUserRole.objects.create(user_id=user_id, role_id=role_id)
#
#             return JsonResponse({'code': 200, 'info': '角色分配成功'})
#         except Exception as e:
#             print(f"角色分配异常：{str(e)}")
#             return JsonResponse({'code': 500, 'info': '角色分配失败，请重试'})



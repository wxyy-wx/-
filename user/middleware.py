# user/middleware.py（适配 rest_framework_simplejwt，贴合文档鉴权目的）
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.tokens import AccessToken
# 引用 rest_framework_simplejwt 顶层异常类（所有 Token 相关异常均继承自此类）
from rest_framework_simplejwt.exceptions import TokenError


class JwtAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # 1. 完全保留文档🔶1-346 白名单逻辑（登录接口+媒体路径不验证）
        white_list = ["/user/login"]
        path = request.path

        if path not in white_list and not path.startswith("/media"):
            print("要进行token验证")
            # 2. 保留文档🔶1-177 兼容 "Bearer Token" 格式的逻辑
            token = request.META.get('HTTP_AUTHORIZATION', '')
            if token.startswith('Bearer '):
                token = token.split(' ')[1]

            # 3. 保留文档🔶1-346 无 Token 时的提示逻辑
            if not token:
                return JsonResponse({'code': 401, 'info': '请先登录获取token！'}, status=401)

            try:
                # 4. 保留文档「验证 Token 有效性」的核心逻辑（用 AccessToken 替代文档的 jwt_decode_handler）
                AccessToken(token)
            except TokenError as e:
                # 5. 按文档🔶1-346 错误提示格式，区分 Token 过期与无效
                if "expired" in str(e).lower():
                    return JsonResponse({'code': 401, 'info': 'Token过期，请重新登录！'}, status=401)
                else:
                    return JsonResponse({'code': 401, 'info': 'Token验证失败！'}, status=401)
        else:
            print("不进行token验证")  # 保留文档日志逻辑
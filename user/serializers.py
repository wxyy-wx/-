from rest_framework import serializers
# 1. 按文档规范导入模型：
# - SysUser：user应用自身模型（文档🔶1-30 多模块划分：user模块存用户模型）
# - SysMenu：menu应用跨域模型（文档🔶1-405 多模块划分：menu模块存菜单模型），修正类名大小写（SysMenu而非sysmenu）
from .models import SysUser
from menu.models import SysMenu  # 文档🔶1-405 跨应用模型引用规范


# 2. 用户序列化器：适配 LoginView 中 SysUserSerializer(user).data（文档🔶1-313 序列化规范）
class SysUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SysUser  # 关联user模块的SysUser模型（文档🔶1-313）
        # 按文档🔶1-313 要求：仅返回前端需用字段，与SysUser模型字段匹配（参考文档🔶1-48 SysUser模型字段）
        fields = ['id', 'username', 'avatar', 'email', 'phonenumber', 'status']  # 删除模型中不存在的nickname/is_active，保留实际字段


# 3. 菜单序列化器：适配 LoginView 中 SysMenuSerializer(menu).data（文档🔶1-409 菜单树序列化规范）
class SysMenuSerializer(serializers.ModelSerializer):
    # 嵌套序列化children字段：文档🔶1-409 要求支持树形结构，递归处理子菜单
    children = serializers.SerializerMethodField()

    class Meta:
        model = SysMenu  # 关联menu模块的SysMenu模型（文档🔶1-405）
        # 按文档🔶1-405 SysMenu模型字段：包含菜单树渲染必需字段（parent_id隐含关联，无需显式返回）
        fields = ['id', 'name', 'path', 'icon', 'order_num', 'children']

    # 自定义children序列化逻辑：文档🔶1-409 递归序列化子菜单
    def get_children(self, obj):
        # 判断是否有动态添加的children属性（LoginView中buildTreeMenu方法添加，文档🔶1-408）
        if hasattr(obj, 'children') and obj.children:
            return SysMenuSerializer(obj.children, many=True).data  # 递归序列化子菜单
        return []  # 无children时返回空列表，避免前端解析报错
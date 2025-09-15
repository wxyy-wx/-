# menu/serializers.py（文档🔶1-409 标准序列化器）
from rest_framework import serializers
from .models import SysMenu  # 导入menu应用的SysMenu模型（文档🔶1-405 模型定义）

class SysMenuSerializer(serializers.ModelSerializer):
    # 嵌套序列化：处理菜单树的children字段（文档🔶1-409 嵌套逻辑）
    children = serializers.SerializerMethodField()

    class Meta:
        model = SysMenu  # 关联SysMenu模型
        # 包含文档要求的菜单字段（需与SysMenu模型字段一致，文档🔶1-405）
        fields = ['id', 'name', 'icon', 'parent_id', 'order_num', 'path', 'component', 'menu_type', 'perms', 'children']

    # 自定义children序列化逻辑（文档🔶1-409 递归处理子菜单）
    def get_children(self, obj):
        # 判断当前菜单是否有动态添加的children属性（文档🔶1-408 buildTreeMenu方法动态添加）
        if hasattr(obj, 'children') and obj.children:
            # 递归序列化子菜单（复用当前序列化器，避免额外定义子类）
            return SysMenuSerializer(obj.children, many=True).data
        return []  # 无children时返回空列表，避免前端解析报错
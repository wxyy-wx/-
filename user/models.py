# user/models.py
from django.db import models
# 错误写法：from rest_framework_simplejwt.serializers import ModelSerializer
# 正确写法：从 rest_framework 导入 ModelSerializer
from rest_framework.serializers import ModelSerializer


# Create your models here.

class SysUser(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100, unique=True, verbose_name="用户名")
    password = models.CharField(max_length=100, verbose_name="密码")
    avatar = models.CharField(max_length=255, null=True, verbose_name="用户头像")
    email = models.CharField(max_length=100, null=True, verbose_name="用户邮箱")
    phonenumber = models.CharField(max_length=11, null=True, verbose_name="手机号码")
    login_date = models.DateField(null=True, verbose_name="最后登录时间")
    status = models.IntegerField(null=True, verbose_name="帐号状态（0正常 1停用）")
    create_time = models.DateField(null=True, verbose_name="创建时间", )
    update_time = models.DateField(null=True, verbose_name="更新时间")
    remark = models.CharField(max_length=500, null=True, verbose_name="备注")

    class Meta:
     db_table = "sys_user"

# 序列化类（修正导入后正常使用）
class SysUserSerializer(ModelSerializer):
    class Meta:
        model = SysUser
        fields = '__all__'  # 或指定需要的字段，如 ['id', 'username', 'email']



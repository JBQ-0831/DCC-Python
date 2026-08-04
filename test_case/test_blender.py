import bpy

class SphereDialog(bpy.types.Operator):
    bl_idname = "dialog.sphere_maker"
    bl_label = "球体创建窗口"

    def invoke(self, context, event):
        # 直接弹出对话框
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        layout = self.layout
        layout.label(text="点击按钮生成球体")
        layout.operator("mesh.primitive_uv_sphere_add", text="创建球体")

    def execute(self, context):
        return {'FINISHED'}


# 临时注册并立刻弹出窗口
bpy.utils.register_class(SphereDialog)
# 直接调用弹窗，运行脚本马上弹出
bpy.ops.dialog.sphere_maker('INVOKE_DEFAULT')
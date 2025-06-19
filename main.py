from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
    
    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("Attention")
    async def Attention(self, event: AstrMessageEvent):
        """
        这是一个 Attention 指令
        使用方法:
        /Attention on 开启群聊注意力
        /Attention off 关闭群聊注意力
        """
        pass

    @Attention.command("on")
    async def Attention_on(self, event: AstrMessageEvent):
        """
        开启群聊注意力
        """
        self.offset = 1
        pass

    @Attention.command("off")
    async def Attention_off(self, event: AstrMessageEvent):
        """
        关闭群聊注意力
        """
        self.offset = 0
        pass

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        yield event.plain_result("收到了一条消息。")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""

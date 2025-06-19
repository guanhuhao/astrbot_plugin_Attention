from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.all import (
    Star, Context, register,
    AstrMessageEvent, command_group,  MessageEventResult
)
from astrbot.core.conversation_mgr import Conversation
import json
from astrbot.core.utils.session_waiter import (
    session_waiter,
    SessionFilter,
    SessionController,
)
# from .util.my_session import (
#     session_waiter,
#     SessionFilter,
#     SessionController,
# )
import astrbot.api.message_components as Comp
import time
import asyncio
import os

from astrbot.core.utils.astrbot_path import get_astrbot_data_path

MESSAGE_TIME = {}
HISTORY_LIST = {}
LAST_MESSAGE = {}

@register("attention", "AttentionBot", "群聊注意力管理插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.group_offset = {}
        self.score_threshold = {}
        self.interval = {}

        # 持久化
        self.config_path = os.path.join(get_astrbot_data_path(), "astrbot-attention.json")            
        logger.info(f"load config: {get_astrbot_data_path()}")
        if not os.path.exists(self.config_path):
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write("{}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.group_offset, self.score_threshold, self.interval = json.load(f)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
    
    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @command_group("attention",alias={'群注意力'})
    def Attention(self, event: AstrMessageEvent):
        """
        群聊注意力管理指令
        使用方法:
        /attention on - 开启群聊注意力
        /attention off - 关闭群聊注意力
        /attention status - 查看当前状态
        /attention set_interval <秒数> - 设置回复间隔
        /attention set_temp <数值> - 设置回复欲望(0-100)
        """
        return
    
    @Attention.command("set_interval",alias={'设置回复间隔'})
    async def set_interval(self, event: AstrMessageEvent, interval:float):
        """
        设置机器人主动回复的时间间隔
        参数:
            interval: 回复间隔时间(秒)
        """
        gid = event.get_group_id() if event.get_group_id() else event.unified_msg_origin
        self.interval[gid] = interval
        await self._save_data()
        yield event.plain_result(f"设置主动回复间隔为{self.interval[gid]}秒")

    @Attention.command("set_temp",alias={'设置回复欲望'})
    async def set_temperature(self, event: AstrMessageEvent, score_threshold:float):
        """
        设置机器人回复的阈值
        参数:
            score_threshold: 回复阈值(0-100)，数值越高越容易回复
        """
        gid = event.get_group_id() if event.get_group_id() else event.unified_msg_origin
        self.score_threshold[gid] = score_threshold
        await self._save_data()
        yield event.plain_result(f"设置回复欲望为{self.score_threshold[gid]}，0-100，0为最低，100为最高")

    @Attention.command("on")
    async def Attention_on(self, event: AstrMessageEvent):
        """
        开启群聊注意力
        """
        gid = event.get_group_id() if event.get_group_id() else event.unified_msg_origin
        self.group_offset[gid] = 1
        logger.info(f"当前群聊注意力状态: {self.group_offset[gid]}")
        await self._save_data()
        yield event.plain_result("开启群聊注意力")

    @Attention.command("off")
    async def Attention_off(self, event: AstrMessageEvent):
        """
        关闭群聊注意力
        """
        gid = event.get_group_id() if event.get_group_id() else event.unified_msg_origin
        self.group_offset[gid] = 0
        logger.info(f"当前群聊注意力状态: {self.group_offset[gid]}")
        await self._save_data()
        yield event.plain_result("关闭群聊注意力")

    @Attention.command("status")
    async def Attention_status(self, event: AstrMessageEvent):
        """
        显示当前群聊注意力状态
        """
        gid = event.get_group_id() if event.get_group_id() else event.unified_msg_origin
        if self.group_offset.get(gid) is None:
            self.group_offset[gid] = 0
            self.interval[gid] = 10
            self.score_threshold[gid] = 50
        logger.info(f"当前群聊注意力状态: {self.group_offset[gid]}")
        if self.group_offset[gid] == 1:
            yield event.plain_result(f"已开启群聊注意力，活跃状态，会自主判断是否需要回复消息\n主动回复间隔: {self.interval[gid]}秒\n回复欲望: {self.score_threshold[gid]}")
        else:
            yield event.plain_result(f"已关闭群聊注意力，静默状态，（群聊中只有@的消息才会回复或者以'/'开头的才会回复）\n主动回复间隔: {self.interval[gid]}秒\n回复欲望: {self.score_threshold[gid]}")
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_all_message(self, event: AstrMessageEvent):
        class CustomFilter(SessionFilter):
            def filter(self, event: AstrMessageEvent) -> str:
                return event.get_group_id() if event.get_group_id() else event.unified_msg_origin
            
        @session_waiter(timeout=10, record_history_chains=True) # 注册一个会话控制器，设置超时时间为 10 秒，记录历史消息链 
        async def empty_mention_waiter(controller: SessionController, event: AstrMessageEvent):
            gid = event.get_group_id() if event.get_group_id() else event.unified_msg_origin
            
            controller.keep(timeout=self.interval[gid], reset_timeout=True)
            logger.info(f"update MESSAGE_TIME: controller.ts: {controller.ts} MESSAGE_TIME[gid]: {MESSAGE_TIME[gid]}")
            if MESSAGE_TIME.get(gid) is None:
                MESSAGE_TIME[gid] = controller.ts
                LAST_MESSAGE[gid] = event.message_obj.message_str
                HISTORY_LIST[gid] = controller.get_history_chains()
            elif controller.ts > MESSAGE_TIME[gid]:
                
                MESSAGE_TIME[gid] = controller.ts
                LAST_MESSAGE[gid] = event.message_obj.message_str
                HISTORY_LIST[gid] = controller.get_history_chains()
          
        global LAST_MESSAGE, HISTORY_LIST, MESSAGE_TIME
        gid = event.get_group_id() if event.get_group_id() else event.unified_msg_origin
        if self.group_offset.get(gid) is None:
            self.group_offset[gid] = 0
            self.interval[gid] = 10
            self.score_threshold[gid] = 50
        # logger.info(f"当前群聊注意力状态: {self.offset}")
        if self.group_offset[gid] == 1 and (event.message_obj.message_str[0] != '/'):
            logger.info(f"event.message_str: {event.message_obj.message_str}")
            try:
                LAST_MESSAGE[gid] = event.message_obj.message_str
                HISTORY_LIST[gid] = [[]]
                MESSAGE_TIME[gid] = 0
                await empty_mention_waiter(event=event)
                # logger.info(f"after event.is_wake: {a}")
            except TimeoutError as _: # 当超时后，会话控制器会抛出 TimeoutError
                # yield event.plain_result("你超时了！")
                conversation = ""
                idx = 0

                for i in HISTORY_LIST[gid][0]:
                    conversation += f"{idx}: {i.text}\n"
                    idx += 1
                prompt = f"根据最近5条的对话内容：{conversation}以及最近的这条消息{LAST_MESSAGE[gid]}，判断用户是否在与你交流（他可能再跟之前对话的人进行进一步交流），以及是否需要你回复，给出你判断的意图分数，分数范围为0-100，请直接给出大致分数，然后再大致分数上随机加减0-10的随机数，最后输出只需要输出一个0-100的数字即可"
                score = await self.context.get_using_provider().text_chat(
                        prompt=prompt,
                        system_prompt="",
                        image_urls=[], # 图片链接，支持路径和网络链接
                    )
                score = score.completion_text
                
                logger.info(f"score_threshold: {100-self.score_threshold[gid]} 回复概率: {int(score)}")
                if int(score) > 100 - self.score_threshold[gid]:
                    prompt = f"根据最近5条的对话内容：{conversation}，返回对最新信息 {LAST_MESSAGE[gid]} 的回复，直接回复，不要输出任何解释"
                    yield event.request_llm(
                        prompt=prompt,
                        system_prompt="",
                        # conversation=conversation
                    )

            except Exception as e:
                logger.error(f"empty_mention_waiter 异常: {e}")
                # return        
            finally:
                event.stop_event()
            logger.info(f"HISTORY_LIST: {HISTORY_LIST}")

        
    async def _save_data(self):
        """Save the subscribe data."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump([self.group_offset, self.score_threshold, self.interval], f, ensure_ascii=False)

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        await self._save_data()

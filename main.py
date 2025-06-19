import aiohttp
import traceback
import re
import os
import json
import uuid
import datetime
import zoneinfo

from astrbot.api.all import (
    Star, Context, register,
    AstrMessageEvent, command_group,  MessageEventResult
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter
from astrbot.api import logger, llm_tool
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from typing import Optional

def format_weather_info(city: str, weather_dict):
  """
  使用正则表达式模板构造天气描述
  """
  # 获取当前时间戳
  current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  
  # 定义天气描述模板
  template = f"当前时间:{current_time} 地点:" + city + r" {date} 周{week} 天气预报：白天{dayweather}，气温{daytemp}°C ~ {nighttemp} °C, {daywind}风{daypower}级；夜间{nightweather}， {nightwind}风{nightpower}级。"
  
  # 使用正则表达式替换占位符
  pattern = r'\{(\w+)\}'
  
  def replace_func(match):
      key = match.group(1)
      return str(weather_dict.get(key, f'{{{key}}}'))
  
  result = re.sub(pattern, replace_func, template)

  return result

@register(
    "daily_weather",
    "Guan",
    "一个基于高德开放平台API的天气查询插件",
    "1.0.0",
    "https://github.com/guanhuhao/astrbot_plugin_daily_weather.git"
)
class WeatherPlugin(Star):
    """
    这是一个调用高德开放平台API的天气查询和订阅插件。
    支持以下命令：
    - /weather [城市]: 查询指定城市的天气预报
    - /weather_subscribe subscribe [描述]: 订阅天气预报
    - /weather_subscribe ls: 查看当前订阅列表
    - /weather_subscribe rm <序号>: 删除指定序号的订阅
    """
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        # 使用配置中的 amap_api_key
        self.api_key = config.get("amap_api_key", "")
        self.default_city = config.get("default_city", "北京")
        # 新增配置项：send_mode，控制发送模式 "image" 或 "text"
        self.send_mode = config.get("send_mode", "image")
        logger.debug(f"WeatherPlugin initialized with API key: {self.api_key}, default_city: {self.default_city}, send_mode: {self.send_mode}")

        # subscribe init
        self.timezone = self.context.get_config().get("timezone")
        if not self.timezone:
            self.timezone = None
        try:
            self.timezone = zoneinfo.ZoneInfo(self.timezone) if self.timezone else None
        except Exception as e:
            logger.error(f"时区设置错误: {e}, 使用本地时区")
            self.timezone = None
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        subscribe_file = os.path.join(get_astrbot_data_path(), "astrbot-subscribe.json")
        if not os.path.exists(subscribe_file):
            with open(subscribe_file, "w", encoding="utf-8") as f:
                f.write("{}")
        with open(subscribe_file, "r", encoding="utf-8") as f:
            self.subscribe_data = json.load(f)

        self._init_scheduler()
        self.scheduler.start()

    def _init_scheduler(self):
        """Initialize the scheduler."""
        for group in self.subscribe_data:
            for subscribe in self.subscribe_data[group]:
                if "id" not in subscribe:
                    id_ = str(uuid.uuid4())
                    subscribe["id"] = id_
                else:
                    id_ = subscribe["id"]
                if "datetime" in subscribe:
                    if self.check_is_outdated(subscribe):
                        continue
                    self.scheduler.add_job(
                        self._subscribe_callback,
                        id=id_,
                        trigger="date",
                        args=[group, subscribe],
                        run_date=datetime.datetime.strptime(
                            subscribe["datetime"], "%Y-%m-%d %H:%M"
                        ),
                        misfire_grace_time=60,
                    )
                elif "cron" in subscribe:
                    self.scheduler.add_job(
                        self._subscribe_callback,
                        trigger="cron",
                        id=id_,
                        args=[group, subscribe],
                        misfire_grace_time=60,
                        **self._parse_cron_expr(subscribe["cron"]),
                    )
                    
    def check_is_outdated(self, subscribe: dict):
        """Check if the subscribe is outdated."""
        if "datetime" in subscribe:
            subscribe_time = datetime.datetime.strptime(
                subscribe["datetime"], "%Y-%m-%d %H:%M"
            ).replace(tzinfo=self.timezone)
            return subscribe_time < datetime.datetime.now(self.timezone)
        return False


    async def use_LLM(self, result: str, config: dict) -> str:
        """
        使用 LLM 服务来润色天气预报结果
        Args:
            result: 原始天气预报文本
            config: LLM配置信息
        Returns:
            str: 润色后的天气预报文本
        """
        try:
            # 构建 prompt
            if len(self.config.get("LLM_prompt", "")) < 5:
                prompt = f"""
                {result}
                请根据上面天气预报信息，润色天气预报文本，但保持信息准确性：
                
                要求：
                1. 天气现象描述要专业,使用适当emoji
                2. 可以根据天气提供小提示（列点），要让人感觉到很贴心温暖
                3. 保持所有数据的准确性
                4. 控制在150字以内
                5. 语气要以可爱的女生语气，给人带来活力满满的能量，但不要太做作
                6. 禁止使用** 或者 # 等markdown格式

                例子：
                2024-03-19 周二 天气小播报（杭州） 预报时间：09:00:00
                大家早安哦~ 今天白天是超美的晴天☀️呢！气温在25°C~15°C之间波动，晚上转为多云，今天风蛮大的，早上东南风3级，晚上西北风2级，记得多穿件外套哦~
                
                小贴士：
                - 今天温差有点大，记得带件外套呀~
                - 白天阳光超好，防晒霜别忘记涂哦！
                - 晚上多云很舒服，适合和朋友出去走走
                
                这么好的天气，心情都会变得超棒的！记得好好享受这个美丽的春日～
                
                """
            else:
                prompt = result + "\n" + "请根据上面天气预报信息，润色天气预报文本，但保持信息准确性：" + "\n" + self.config.get("LLM_prompt", "")

            result = await self.context.get_using_provider().text_chat(
                    prompt=prompt,
                    # func_tool_manager=func_tools_mgr,
                    # session_id=curr_cid, # 对话id。如果指定了对话id，将会记录对话到数据库
                    # contexts=context, # 列表。如果不为空，将会使用此上下文与 LLM 对话。
                    system_prompt="",
                    image_urls=[], # 图片链接，支持路径和网络链接
                    # conversation=conversation # 如果指定了对话，将会记录对话
                )
            result = result.completion_text
            return result

        except Exception as e:
            logger.error(f"LLM enhancement failed: {e}")
            logger.error(traceback.format_exc())
            return result


    # =============================
    # 命令组 "weather"
    # =============================
    @filter.command("weather", alias={'天气'})
    async def weather_current(self, event: AstrMessageEvent, city: Optional[str] = "杭州"):
        """
        查看城市天气预报信息
        用法: /weather [城市]
        示例: /weather 北京
        说明: 如果不指定城市，将使用默认城市
        """
        logger.info(f"User called /weather current with city={city}")
        if not city:
            city = self.default_city
        if not self.api_key:
            yield event.plain_result("未配置 Amap API Key，无法查询天气。请在管理面板中配置后再试。")
            return
        data = await self.get_future_weather_by_city(city)
        if data is None:
            yield event.plain_result(f"查询 [{city}] 的当前天气失败，请稍后再试。")
            return
        
        # 根据配置决定发送模式
        if self.send_mode == "image":
            result_img_url = await self.render_current_weather(data)
            yield event.image_result(result_img_url)
        else:
            text = format_weather_info(city, data[0])
            # 使用 LLM 润色结果
            logger.info(f"original weather text={text}")
            enhanced_text = await self.use_LLM(text, self.config)
            logger.info(f"LLM enhanced weather text={enhanced_text}")
            yield event.plain_result(enhanced_text)


        # =============================
    
    
    # 命令组 "weather_subscribe"
    # =============================
    @command_group("weather_subscribe", alias={'天气订阅'})
    def weather_subscribe_group(self):
        """
        天气订阅相关功能命令组。
        使用方法：
        /weather_subscribe <子指令> [参数]
        子指令包括：
        - subscribe: 订阅天气预报
        - ls: 查看订阅列表
        - rm: 删除指定订阅
        """
        pass
    @weather_subscribe_group.command("subscribe", alias={'订阅'})
    async def weather_subscribe(self, event: AstrMessageEvent, description: str = ""):
        """
        订阅天气预报
        用法: /weather subscribe <城市>
        示例: /weather subscribe 北京
        """
        city = "上海"
        cron_expression = "0 9 * * *"
        human_readable_cron = "每天9点"

        if description != "":
            city = await self.context.get_using_provider().text_chat(
                prompt=description,
                # func_tool_manager=func_tools_mgr,
                # session_id=curr_cid, # 对话id。如果指定了对话id，将会记录对话到数据库
                # contexts=context, # 列表。如果不为空，将会使用此上下文与 LLM 对话。
                system_prompt="请分析提取出城市名称,只需要输出城市名称如 杭州",
                image_urls=[], # 图片链接，支持路径和网络链接
                # conversation=conversation # 如果指定了对话，将会记录对话
            )
            city = city.completion_text

            cron_expression = await self.context.get_using_provider().text_chat(
                prompt=description,
                system_prompt="请分析提取出cron表达式，只需要输出cron表达式如 0 9 * * *",
                image_urls=[], # 图片链接，支持路径和网络链接
                # conversation=conversation # 如果指定了对话，将会记录对话
            )
            cron_expression = cron_expression.completion_text

            human_readable_cron = await self.context.get_using_provider().text_chat(
                prompt=city + " " + cron_expression,
                system_prompt="将输入的地点和时间转换为人类可读的格式，方便人理解，字数限制在20个字以内",
                image_urls=[], # 图片链接，支持路径和网络链接
                # conversation=conversation # 如果指定了对话，将会记录对话
            )
            human_readable_cron = human_readable_cron.completion_text


        logger.info(f"city={city}, cron_expression={cron_expression}, human_readable_cron={human_readable_cron}")


        d = {
            "text": "天气预报",
            "cron": cron_expression,
            "cron_h": human_readable_cron,
            "id": str(uuid.uuid4()),
            "city": city,
        }
        if event.unified_msg_origin not in self.subscribe_data:
            self.subscribe_data[event.unified_msg_origin] = []
        self.subscribe_data[event.unified_msg_origin].append(d)
        self.scheduler.add_job(
            self._subscribe_callback,
            "cron",
            id=d["id"],
            misfire_grace_time=60,
            **self._parse_cron_expr(cron_expression),
            args=[event.unified_msg_origin, d],
        )
        await self._save_data()
        yield event.plain_result(f"{human_readable_cron} 订阅成功")
    
    def _parse_cron_expr(self, cron_expr: str):
        logger.info(f"cron_expr={cron_expr}")
        fields = cron_expr.split(" ")
        return {
            "minute": fields[0],
            "hour": fields[1],
            "day": fields[2],
            "month": fields[3],
            "day_of_week": fields[4],
        }

    async def _subscribe_callback(self, unified_msg_origin: str, d: dict):
        """The callback function of the subscribe."""
        import datetime
        
        logger.info("🔔 订阅回调函数被触发！")

        try:
            city = d.get("city", "苏州")
            data = await self.get_future_weather_by_city(city)
            
            if data is None:
                logger.error(f"查询 [{city}] 的当前天气失败")
                return
            
            # 根据配置决定发送模式
            if self.send_mode == "image": # TODO
                result_img_url = await self.render_current_weather(data)
                # 发送图片消息
                await self.context.send_message(
                    unified_msg_origin,
                    MessageEventResult().image(result_img_url)
                )
            else:
                text = format_weather_info(city, data[0])
                logger.info(f"original weather text={text}")
                # 使用 LLM 润色结果
                enhanced_text = await self.use_LLM(text, self.config)
                logger.info(f"LLM enhanced weather text={enhanced_text}")
                await self.context.send_message(
                    unified_msg_origin,
                    MessageEventResult().message(enhanced_text)
                )
                
            logger.info(f"天气订阅推送成功: {city}")
            
        except Exception as e:
            logger.error(f"订阅回调执行失败: {e}", exc_info=True)
    
    @weather_subscribe_group.command("ls", alia={"展示"})
    async def subscribe_list(self, event: AstrMessageEvent, city: Optional[str] = ""):
        """List upcoming subscribe."""
        subscribe = await self.get_upcoming_subscribe(event.unified_msg_origin)
        if not subscribe:
            yield event.plain_result("没有正在进行的订阅事项。")
        else:
            subscribe_str = "正在进行的订阅事项：\n"
            for i, subscribe in enumerate(subscribe):
                time_ = subscribe.get("datetime", "")
                if not time_:
                    cron_expr = subscribe.get("cron", "")
                    time_ = subscribe.get("cron_h", "") + f"(Cron: {cron_expr})"
                subscribe_str += f"{i + 1}. {subscribe['text']} - {time_}\n"
            subscribe_str += "\n使用 /weather_subscribe rm <id> 删除订阅事项。\n"
            yield event.plain_result(subscribe_str)

    @weather_subscribe_group.command("rm", alias={"删除"})
    async def subscribe_rm(self, event: AstrMessageEvent, index: int):
        """Remove a subscribe by index."""
        subscribe = await self.get_upcoming_subscribe(event.unified_msg_origin)

        if not subscribe:
            yield event.plain_result("没有待办事项。")
        elif index < 1 or index > len(subscribe):
            yield event.plain_result("索引越界。")
        else:
            subscribe = subscribe.pop(index - 1)
            job_id = subscribe.get("id")

            users_subscribe = self.subscribe_data.get(event.unified_msg_origin, [])
            for i, s in enumerate(users_subscribe):
                if s.get("id") == job_id:
                    users_subscribe.pop(i)

            try:
                self.scheduler.remove_job(job_id)
            except Exception as e:
                logger.error(f"Remove job error: {e}")
                yield event.plain_result(
                    f"成功移除对应的待办事项。删除定时任务失败: {str(e)} 可能需要重启 AstrBot 以取消该提醒任务。"
                )
            await self._save_data()
            yield event.plain_result("成功删除待办事项：\n" + subscribe["text"])

    async def get_upcoming_subscribe(self, unified_msg_origin: str):
        """Get upcoming subscribe."""
        subscribe = self.subscribe_data.get(unified_msg_origin, [])
        if not subscribe:
            return []
        now = datetime.datetime.now(self.timezone)
        upcoming_subscribe = [
            subscribe
            for subscribe in subscribe
            if "datetime" not in subscribe
            or datetime.datetime.strptime(
                subscribe["datetime"], "%Y-%m-%d %H:%M"
            ).replace(tzinfo=self.timezone)
            >= now
        ]
        return upcoming_subscribe

    async def _save_data(self):
        """Save the subscribe data."""
        subscribe_file = os.path.join(get_astrbot_data_path(), "astrbot-subscribe.json")
        with open(subscribe_file, "w", encoding="utf-8") as f:
            json.dump(self.subscribe_data, f, ensure_ascii=False)
    
    
    # =============================
    # 核心逻辑
    # =============================
    async def get_future_weather_by_city(self, city: str) -> Optional[list]:
        """
        调用高德开放平台API，获取城市未来天气预报信息
        Args:
            city: 城市名称
        Returns:
            Optional[list]: 天气预报信息列表，如果获取失败则返回None
        """
        logger.debug(f"get_current_weather_by_city city={city}")
        url = "https://restapi.amap.com/v3/weather/weatherInfo"
        params = {
            "key": self.api_key,
            "city": city,
            "extensions": "all"
        }
        logger.debug(f"Requesting: {url}, params={params}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    logger.debug(f"Response status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        weather_list = []
                        for daily_weather in data['forecasts'][0]['casts']:
                              weather_list.append(daily_weather)

                        return weather_list
                    else:
                        logger.error(f"get_current_weather_by_city status={resp.status}")
                        return None
        except Exception as e:
            logger.error(f"get_current_weather_by_city error: {e}")
            logger.error(traceback.format_exc())
            return None

    async def terminate(self):
        self.scheduler.shutdown()
        await self._save_data()
        logger.info("weather_subscribe plugin terminated.")
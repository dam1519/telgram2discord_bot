import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import discord
from discord.ext import commands
from abc import ABC, abstractmethod
import asyncio

class IMessenger(ABC):
    @abstractmethod
    def __init__(self, token: str, chat_id: str, queue: asyncio.Queue):
        pass

    @abstractmethod
    async def get_msg(self, msg: str):
        pass

    @abstractmethod
    async def send_msg(self, msg_text: str):
        pass

class TelegramSide(IMessenger):

    def __init__(self, token: str, chat_id: str, queue: asyncio.Queue):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.chat = int(chat_id)
        self.queue = queue
        self.handlers()

    def handlers(self):
        self.dp.message(Command("start"))(self.start)

        self.dp.message()(self._msg_tg_get)

    async def start(self, message: types.Message):
        await message.answer("ПРИВЕТ ЗДОРОВЯЯК!!! Я ПРИШЕЛ ЧТОБЫ ПОСПАТЬ С ТОБОЙ ПОД ОДНИМ ОДЕЯЛКОМ! БЕЗ ОДЕЖДЫ! ТОЛЬКО НАДЕНЬ ТЕ КОШАЧЬИ УШКИ ЧТО Я ТЕБЕ ДАРИЛ! Я ЖЕ ЗНАЮ ЧТО ТЫ ЭТО ТАК ХОЧЕШЬ! ДАВАЙ! ДАВАЙ! ДАВАЙ!.")

    async def _msg_tg_get(self, msg: types.Message):
        if not msg.from_user.is_bot and msg.chat.id == self.chat:
            await self.send_msg(msg.text)

    async def send_msg(self, msg_text: str):
        msg = {"id" : "tg", "text" : msg_text}
        await self.queue.put(msg)

    async def get_msg(self, msg: str):
        await self.bot.send_message(chat_id=self.chat, text=msg)

    async def start_tg_bot(self):
        await self.bot.delete_webhook(drop_pending_updates=True)
        await self.dp.start_polling(self.bot)

class DiscordSide(IMessenger):
    def __init__(self, token: str, chat_id: str, queue: asyncio.Queue):
        self.token = token
        self.chat = int(chat_id)
        self.queue = queue
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='/', intents=intents)
        self.handlers()


    def handlers(self):
        self.bot.add_listener(self._msg_ds_get, name="on_message")

    async def _msg_ds_get(self, msg):
        if msg.author != self.bot.user and msg.channel.id == self.chat:
            if msg.content:
                await self.send_msg(msg.content)

    async def send_msg(self, msg_text: str):
        msg = {"id" : "ds", "text" : msg_text}
        await self.queue.put(msg)

    async def get_msg(self, msg: str):
        chat_id = self.chat

        channel = self.bot.get_channel(chat_id) or await self.bot.fetch_channel(chat_id)
        if channel:
            await channel.send(msg)
        else:
            print("дискорд канал не найден")

    async def start_ds_bot(self):
        await self.bot.start(self.token)

class Bridge:
    def __init__(self, tg_side: IMessenger, ds_side: IMessenger, queue: asyncio.Queue):
        self.tg = tg_side
        self.ds = ds_side
        self.queue = queue
        self._bg_task = None

    async def punct_to_punct(self):
         while True:
             try:
                msg = await self.queue.get()
                try:
                    if msg["id"] == "tg":
                        await self.ds.get_msg(msg["text"])
                    else:
                        await self.tg.get_msg(msg["text"])
                except Exception as e:
                    print(f"ошибко {e}")
                finally:
                    self.queue.task_done()
             except (KeyboardInterrupt, asyncio.CancelledError):
                break


    def start(self):
        if self._bg_task is None:
            self._bg_task = asyncio.create_task(self.punct_to_punct())

    def stop(self):
        if self._bg_task:
            self._bg_task.cancel()
            self._bg_task = None

async def main():
    load_dotenv()
    queue = asyncio.Queue()
    tg_token = os.environ.get("TELEGRAM_TOKEN")
    tg_chat = os.environ.get("TG_CHAT_ID")
    ds_token = os.environ.get("DISCORD_TOKEN")
    ds_chat = os.environ.get("DISCORD_CHAT_ID")
    ds = DiscordSide(ds_token, ds_chat, queue)
    tg = TelegramSide(tg_token, tg_chat, queue)
    bridge = Bridge(tg, ds, queue)

    bridge.start()

    try:
        await asyncio.gather( tg.start_tg_bot(), ds.start_ds_bot())
    finally:
        bridge.stop()

asyncio.run(main())
import requests
import aiohttp
from aiohttp import ClientError, ClientTimeout, ClientConnectorError
from requests import exceptions
import urllib3
import re
from dnevnik_types import *
from greate_logger import Logger as LG

async def get(url, cookies, timeout):
    try:
        async with aiohttp.ClientSession(cookies=cookies, timeout=ClientTimeout(total=timeout)) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
    except Exception as e:
        print(f"EERRRO IN AIOHTTP! {e}")


async def download(url, cookies, timeout):
    try:
        async with aiohttp.ClientSession(cookies=cookies, timeout=ClientTimeout(total=timeout)) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.content.read()
    except Exception as e:
        print(f"EERRRO IN AIOHTTP! {e}")


class Dnevnik:
    api: str = None
    cookies: dict = None
    username: str = None
    password: str = None
    is_ssl_on: bool = None
    logger: LG = None
    def __init__(self, host:str):
        if(not re.match("[0-9a-bA-BА-Яа-яЁё.]*.[a-bA-BА-Яа-яЁё.]*", host)):
            raise RuntimeError("Invalid host!")
        h = f"https://{host}"
        res = None
        self.is_ssl_on = True
        self.logger = LG("Dnevnik", True)
        try:
            res = requests.get(h)
        except exceptions.SSLError as e:
            print(e)
            self.logger.warn(f"Https unavailable, tring http...")
            res = requests.get(h, verify=False)
            self.is_ssl_on = False
            urllib3.disable_warnings()
        if(not res.ok):
            raise ConnectError(f"request status code: {res.status_code}")
        self.logger.log(f"Successfuly init Dnevnik!")
        self.api = h


    async def Login(self, login:str = None, password:str = None):
        if(login == None):
            if(self.username == None): 
                raise RuntimeError("No login provided!")
            login = self.username
        if(password == None):
            if(self.password == None): 
                raise RuntimeError("No password provided!")
            password = self.password
        self.logger.name = f"Dnevnik{{{login}}}"
        res = requests.post(f"{self.api}/login?user-name={login}&user-password={password}", timeout=5000, verify=self.is_ssl_on)
        if(not res.ok):
            raise LoginError(f"Unauthorized {res.text}")
        self.password = password
        self.username = login
        self.cookies = {}
        for n,v in res.cookies.items():
            self.cookies[n] = v
        self.logger.info(f"Logged in successfuly with credentials {login}:{password}")


    async def GetParallels(self) -> list[Parallel]:
        res = await self._get_request_("/webservice/app.cj/execute?action=menu")
        pars: list[Parallel] = []
        for i in res:
            if (i['type_id'] == '0'):
                pars.append(Parallel(i))
        return pars
    
    async def GetLessonInfo(self, journal_id, lesson_id):
        return await self._get_request_(f"/webservice/app.cj/execute?action=lessonget&cj_id={journal_id}&id={lesson_id}")

    async def DownloadFile(self, lesson_id, file_id) -> bytes:
        try:
            res = await self._get_request_(f"/webservice/app.cj/execute?action=fileget&lesson_id={lesson_id}&id={file_id}")
            return res
        except Exception as e: 
            raise RuntimeError(f"Error in get file: {lesson_id}-{file_id} ex: {e}")




    async def GetData(self, data_id: int):
        return await self._get_request_(f"/webservice/app.cj/execute?action=getdata&id={data_id}")
    

    async def GetClasses(self):
        res = await self._get_request_("/webservice/app.cj/execute?action=menu")
        classes: dict[str, list[int]] = {}
        for i in res:
            if (i['type_id'] != '0'): 
                continue
            for j in i['items']:
                for k in j['items']:
                    if (k['type_id'] != '0'): 
                        continue 
                    name = k['name'].replace(' ', '')
                    classes[name] = classes.get(name, []) + [k['id']]
        return classes

                    

    async def _get_request_(self, path) -> list | dict:
        res = None
        try:
            res = await get(f"{self.api}{path}", cookies=self.cookies, timeout=10)
        except Exception:
            await self.Login()
            self.logger.log("[low level] request again")
            res = await get(f"{self.api}{path}", cookies=self.cookies, timeout=10)
        if (res is None):
            raise RuntimeError(f"Error in request({path})")
        return res
    
    async def _download_request_(self, path) -> list | dict:
        res = None
        try:
            res = await download(f"{self.api}{path}", cookies=self.cookies, timeout=10)
        except Exception:
            await self.Login()
            self.logger.log("[low level] request again")
            res = await download(f"{self.api}{path}", cookies=self.cookies, timeout=10)
        if (res is None):
            raise RuntimeError(f"Error in request({path})")
        return res


import requests
import re
from dnevnik_types import *

class Dnevnik:
    api:str = None
    cookies:dict = None
    username:str = None
    password:str = None
    def __init__(self, host:str):
        if(not re.match("[0-9a-bA-BА-Яа-яЁё.]*.[a-bA-BА-Яа-яЁё.]*", host)):
            raise RuntimeError("Invalid host!")
        h = f"https://{host}"
        res = requests.get(h)
        if(not res.ok):
            raise ConnectError(f"request status code: {res.status_code}")
        print(f"Successfuly init Dnevnik!")
        self.api = h


    def Login(self, login:str = None, password:str = None):
        if(login == None):
            if(self.username == None): raise RuntimeError("No login provided!")
            login = self.username
        if(password == None):
            if(self.password == None): raise RuntimeError("No password provided!")
            password = self.password
        
        res = requests.post(f"{self.api}/login?user-name={login}&user-password={password}", timeout=5000)
        if(not res.ok):
            raise LoginError(f"Unauthorized {res.text}")
        self.password = password
        self.username = login
        self.cookies = {}
        for n,v in res.cookies.items():
            self.cookies[n] = v
        print(f"Logged in successfuly with credentials {login}:{password}")


    def GetParallels(self) -> list[Parallel]:
        res = self._get_request_("/webservice/app.cj/execute?action=menu").json()
        pars:list[Parallel] = []
        for i in res:
            if (i['type_id'] == '0'):
                pars.append(Parallel(i))
        return pars
    
    def GetLessonInfo(self, journal_id, lesson_id):
        return self._get_request_(f"/webservice/app.cj/execute?action=lessonget&cj_id={journal_id}&id={lesson_id}").json()

    def DownloadFile(self, lesson_id, file_id) -> bytes:
        res = self._get_request_(f"/webservice/app.cj/execute?action=fileget&lesson_id={lesson_id}&id={file_id}")
        if not (res.ok):
            raise RuntimeError(f"Error in get file: {res.text}")
        
        return res.content




    def GetData(self, data_id:int):
        return self._get_request_(f"/webservice/app.cj/execute?action=getdata&id={data_id}").json()
    

    def GetClasses(self):
        res = self._get_request_("/webservice/app.cj/execute?action=menu").json()
        classes:dict[str, list[int]] = {}
        for i in res:
            if (i['type_id'] != '0'): continue
            for j in i['items']:
                for k in j['items']:
                    if (k['type_id'] != '0'): continue 
                    name = k['name'].replace(' ', '')
                    classes[name] = classes.get(name, []) + [k['id']]
        return classes

                    

    def GetClassMarks(self, class_name:str):
        parallels = self.GetClasses()
        for i in parallels:
            if(i.name == class_name):
                i.p_id
                break


    def _get_request_(self, path):
        print("[low level] request")
        res = requests.get(f"{self.api}{path}", cookies=self.cookies, timeout=10)
        if(res.status_code == 401):
            self.Login()
            print("[low level] request again")
            res = requests.get(f"{self.api}{path}", cookies=self.cookies, timeout=10)
        if(not res.ok):
            raise RuntimeError(f"Error in request({path}): status: {res.status_code} answer: {res.text}")
        print("[low level] answer")
        return res


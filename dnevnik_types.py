class DObj:
    raw_data:dict = None

    def __init__(self, data:dict):
        self.raw_data = data
    def __str__(self):
        return f"{self.raw_data}"


class Clazz(DObj):
    name:str = None
    #great = None
    #letter = None
    c_id = None
    grade_id = None
    type_id = None
    stream = None
    rmask = None
    def __init__(self, data:dict):
        super().__init__(data)
        self.name = data['name']
        self.c_id = data['id']
        self.type_id = data['type_id']
        self.grade_id = data['grade_id']
        self.stream = data['stream']
        self.rmask = data['rmask']

class Subject(DObj):
    s_id:str = None
    type_id = None
    name:str = None
    items:list[Clazz] = None  
    def __init__(self, data:dict):
        super().__init__(data)
        self.name = data['name']
        self.s_id = data['id']
        self.type_id = data['type_id']
        self.items:list[Clazz] = []
        for i in data['items']:
            self.items.append(Clazz(i))

class Parallel(DObj):
    name:str = None
    p_id:str = None
    type_id:str = None
    items:list[Subject]
    def __init__(self, data:dict):
        super().__init__(data)
        self.name = data['name']
        self.p_id = data['id']
        self.type_id = data['type_id']
        self.items = []
        for i in data['items']:
            self.items.append(Subject(i))



#ERRORS

class ConnectError(Exception):
    ...

class InternalError(Exception):
    ...

class LoginError(Exception):
    ...
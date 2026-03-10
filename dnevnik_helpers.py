

def GetOrCreateDnevnik(host, login, password) -> Dnevnik:
    id = GenerateDID(host, login, password)
    r = dnevniks.get(id)
    if r == None:
        print("Dnevnik not found, creating...")
        k = Dnevnik(host)
        k.Login(login, password)
        dnevniks[id] = k
        return k
    return r

def GetShortcutId(text:str):
    cursor.execute("INSERT OR IGNORE INTO shortcuts (text) VALUES (?)", (text,))
    cursor.execute("SELECT id FROM shortcuts WHERE text = ?", (text,))
    return cursor.fetchone()[0]

def GetShortcutText(id:int):
    cursor.execute("SELECT text FROM shortcuts WHERE id = ?", (id,))
    r = cursor.fetchone()
    if(r == None):
        return f"NOT FOUND SHR({id})"
    return r[0]

def GenerateDID(website, login, password) -> str:
    return hashlib.md5(f"{website}!{login}~{password}".encode('utf-8')).hexdigest()

def GetTypeFromId(type_id:str, data:list[dict]):
    for i in data:
        if (type_id == i['id']):
            return i
    return {"id": f"{type_id}", "name":f"id[{type_id}] not found!", 'mask': '-1', 'shortname':'nf', 'cost':'0','desc':'NOT FOUND, DEV is dump'}

def GetMarkFromId(type_id:str, data:list[dict]):
    for i in data:
        for j in i['marks']:
            if (type_id == j['id']):
                return j
    return {'id':'-999', 'name': 'nf', 'cost':'0', 'key':'-1'}

import time
import asyncio
import hashlib
import uuid
import os
from telegram.ext import ApplicationBuilder
from datetime import datetime
from dnevnik import *
from dnevnik_types import *
from dotenv import load_dotenv 

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PASSWORD = os.getenv("PASSWORD")
WEB_APP_URL = os.getenv("WEBAPP")
DB_FILENAME = 'ed.db'



dnevniks:dict[str, Dnevnik] = {}
time_to_sleep = 0



async def mainLoop():
    global time_to_sleep
    while True:
        time_to_sleep = 60*60
        while time_to_sleep > 0:
            current_h = datetime.now().hour
            print(f"\033[1A\r\033[K{time_to_sleep}")
            if(current_h > 23 or current_h < 5):
                await asyncio.sleep(1)
            await asyncio.sleep(1)
            time_to_sleep -= 1
            if(time_to_sleep%10 == 0):  
                try:
                    await EventProc()
                except: pass
        await UpdateData()

async def UpdateData():
    cursor.execute("SELECT id, school, class_name, website, login, password, teacher_tid FROM dnevniks WHERE is_active = 1")
    sql_answer = cursor.fetchall()
    for i in sql_answer:
        try:
            d:Dnevnik = None
            jid = i[0]
            school = i[1]
            class_name = i[2]
            website = i[3]
            login = i[4]
            password = i[5]
            teacher_tid = i[6]
            try:
                d = GetOrCreateDnevnik(website, login, password)
            except ConnectError as e:
                print(f"Error in connection to school website: {e}")
            except LoginError:
                cursor.execute("UPDATE dnevniks SET is_active = 0 WHERE id = ?", (jid,))
                await application.bot.send_message(teacher_tid, f"<b>Внимание!</b>\nКажется у вас сменились логин или пароль к ЭД!\nИх необходимо обновить в боте, иначе ваш класс не сможет им пользоваться!\n<blockquote>Школа: {school}\nКласс: {class_name}\nВебсайт: {website}</blockquote>\n<i>При возникновении затруднений, обращайтесь к разработчику!</i>",parse_mode='HTML', reply_markup=InlineKeyboardMarkup[[InlineKeyboardButton("Редактировать", callback_data=f"edit_journal_t:{i[0]}")], DEV_BUTTON])
                # cursor.execute("SELECT tid FROM students WHERE status = \"student\"")
                # for j in cursor.fetchall():
                #     pass
            except Exception as e:
                print(f"Unexpected failture: {e}")
            classes = d.GetClasses()
            for k,v in classes.items():
                if (not k.startswith(class_name)): continue
                for j in v:
                    t = time.time()
                    data = d.GetData(j)
                    print(f"\tGetData complited in {time.time()-t}")
                    t = time.time()
                    journal = data['journal']
                    subject = journal['subject_name']
                    members = data['members']
                    periods:list[dict] = data['periods']
                    subject_shr = GetShortcutId(subject)
                    teacher_name = journal['teacher_name']
                    print(f"Processing subject {subject}, teacher: {teacher_name}")
                    cursor.execute("SELECT COUNT(*) FROM periods WHERE school = ? AND class_name = ?",
                                   (school, class_name))
                    pcount = cursor.fetchone()[0]
                    print("\tAdding periods...")
                    if (pcount != len(periods)):
                        for n, i in enumerate(periods, start=1):
                            cursor.execute("INSERT OR IGNORE INTO periods (school, class_name, date_from, date_to, number) VALUES (?, ?, ?, ?, ?)", 
                                           (school, class_name, i['date_from'], i['date_to'], n))
                    excluded = set()
                    print("\tExcluding students...")
                    for i in members:
                        movements = i['movements'][-1]
                        if (movements['date_out'] != ''):
                            excluded.add(i['id'])
                            cursor.execute("SELECT tid FROM students WHERE school = ? AND class_name = ? AND student_id = ?", 
                                           (school, class_name, i['id'])
                                           )
                            student = cursor.fetchone()
                            if (student is not None):
                                cursor.execute("DELETE FROM students WHERE class_name = ? AND school = ? AND student_id = ?",
                                               (class_name, school, i['id'])
                                               )
                            continue
                        if(k != class_name):
                            cursor.execute("INSERT OR IGNORE INTO class_linking (school, class_name, student_id, subject_shr, group_name) VALUES (?, ?, ?, ?, ?)", 
                                            (school, class_name, i['id'], subject_shr, k)
                                           )
                    
                    print("\tProcessing lessons...")
                    lessons:list[dict] = data['lessons']
                    lsndate = {}
                    for i in lessons:
                        lesson_id:str = i['id']
                        lsndate[lesson_id] = i['date']
                        sus = i['lt'] # check for final lesson and V-type lesson
                        if (sus != ''):
                            print('\t\tskipping')
                            continue
                        typ = GetTypeFromId(i['lesson_type'], data['lesson_types'])
                        cursor.execute("SELECT homework FROM lessons WHERE school = ? AND id = ?", (school, lesson_id))
                        al = cursor.fetchone()
                        if(al != None):
                            if(al[0] != i['homework']):
                                cursor.execute("UPDATE lessons SET homework = ? WHERE school = ? AND id = ?", (i['homework'], school, lesson_id))
                        if(datetime.strptime(i['date'], '%Y-%m-%d').date() > datetime.now().date() - timedelta(7)):
                            asyncio.create_task(PostProcessLesson(website, login, password, school, k, j, lesson_id))
                        cursor.execute("INSERT OR IGNORE INTO lessons (school, class_name, id, type_shr, subject_shr, num, homework, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                       (school, k, lesson_id, GetShortcutId(typ['name']), subject_shr, int(i['num']), i['homework'], i['date'])
                                       )
                        #print(f"\tAdded lesson {lesson_id}")
                    print("\tProcessing controls...")
                    controls:list[dict[str, str]] = data['controls']
                    ctrls:dict[str, dict[str, str]] = {}
                    for i in controls:
                        ctrls[i['id']] = {
                            'lesson_id': i['lesson_id'],
                            'type_id': i['type_id'],
                            'cost': i['cost'],
                            'text': i['text'],
                            'short': i.get('short', '')
                        }
                    print("\tPhantoming marks...")
                    marks = data['marks']
                    real_marks = set()
                    cursor.execute("SELECT mark_id FROM marks WHERE school = ? AND subject_shr = ? AND student_id IN (SELECT student_id FROM students WHERE school = ? AND class_name = ? UNION SELECT student_id FROM class_linking WHERE school = ? AND group_name = ? AND subject_shr = ?)", 
                                   (school, subject_shr, school, k, school, k, subject_shr)
                                   )
                    phantom_marks:set[int] = set([i[0] for i in cursor.fetchall()])
                    mark_type_cache = {}
                    print("\tProcessing mark types...")
                    for i in data['mark_types']:
                        for j in i['marks']:
                            mark_type_cache[j['id']] = {
                                'name': j['name'],
                                'shortname': j['shortname'],
                                'cost': float(j['cost']),
                                'key': j['key']
                            }
                    mark_type_cache['-1'] = {
                        'name': 'замечание',
                        'shortname': 'замеч.',
                        'cost': 0,
                        'key': '!'
                    }
                    print("\tProcessing marks...")
                    for i in marks:
                        m_id:str = i['id'] 
                        if (i['student_id'] in excluded): continue
                        real_marks.add(int(m_id))
                        if (int(m_id) in phantom_marks): continue
                        control_id:str = i['control_id']
                        control = ctrls[control_id]
                        key = mark_type_cache.get(i['type_id'], {'key': 'NF', 'shortname': 'NOT FOUND', 'cost': 0})
                        typ = None
                        if (control_id.startswith('f')):
                            typ = {
                                'shortname': control['short'],
                                'cost': control['cost']
                            }
                            i['text'] = 'pSS:f1nAl'
                        else:
                            typ = GetTypeFromId(control['type_id'], data['control_types'])
                        print(f"\t\tmark_typ: {type(typ)}  mark_key: {type(key)}")
                        cursor.execute("INSERT OR IGNORE INTO marks (school, mark_id, mark_char, shortname, subject_shr, student_id, value, cost, text, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (school, m_id, key['key'], typ['shortname'], subject_shr, i['student_id'], float(key['cost']), float(typ['cost']), i['text'], lsndate[control['lesson_id']])
                                    )
                        
                    print("\tMatching marks...")
                    print(f"\t\t{len(phantom_marks)}")
                    print(f"\t\t{len(real_marks)}")
                    for i in phantom_marks:
                        if not i in real_marks:
                            print(f"\t\tdeleting mark {i}")
                            cursor.execute("DELETE FROM marks WHERE school = ? AND mark_id = ?", (school, i))
                    print(f"\tData parsing complited in {time.time()-t}\n\tSleeping...")
                    time.sleep(2)
        except Exception as e:
            print(f"fatal exception happend: {e}")
    last_update["stop"] = time.time()

async def EventProc():
    cursor.execute("SELECT id, type, school, class, subject_shr, student_id, lesson_id, mark_id, extra, affected_date FROM events ORDER BY student_id LIMIT 30")
    events = cursor.fetchall()
    if len(events) == 0: return
    msgs = {}
    for i in events:
        try:
            event_type:str = i[1]
            school:int = i[2]
            class_name:str = i[3]
            subject_shr:int = i[4]
            student_id:int = i[5]
            lesson_id:int = i[6]
            mark_id:int = i[7]
            extra:str = i[8]
            date = i[9]
            print(f"Processing {event_type} event: {i}")
            if (event_type == 'lesson_added'):
                if (extra.strip() == ''):
                    continue
                cursor.execute("SELECT tid FROM students WHERE tid != 0 AND send_dz = 1 AND school = ? AND (class_name = ? OR student_id IN (SELECT student_id FROM class_linking WHERE school = ? AND subject_shr = ? AND group_name = ?))", (school, class_name, school, subject_shr, class_name))
                students = cursor.fetchall()
                for j in students:
                    a = msgs.get(j[0], "<b>Новая информация!</b>:\n")
                    a+=f"Новое дз по <i>{GetShortcutText(subject_shr)}</i> от {date}:\n<blockquote expandable>{extra}</blockquote>\n"
                    msgs[j[0]] = a
            elif (event_type == 'mark_added'):
                cursor.execute("SELECT tid FROM students WHERE school = ? AND send_marks = 1 AND student_id = ? AND tid != 0", (school, student_id, ))
                student = cursor.fetchone()
                if (student):
                    cursor.execute("SELECT mark_char, value, cost, text FROM marks WHERE school = ? AND mark_id = ?", (school, mark_id))
                    mark = cursor.fetchone()
                    if(mark):
                        if(mark[0] != '' and mark[1] != 0):
                            a = msgs.get(student[0], "<b>Новая информация!</b>:\n")
                            a+=f"Новая оценка по <i>{GetShortcutText(subject_shr)}</i>\n   Оценка: <b><u>{mark[0]}</u></b> за {extra} с коэффициентом {mark[2]}\n"
                            msgs[student[0]] = a
            elif (event_type == 'mark_deleted'):
                cursor.execute("SELECT tid FROM students WHERE school = ? AND send_marks = 1 AND student_id = ? AND tid != 0", (school, student_id, ))
                student = cursor.fetchone()
                if(student):
                    a = msgs.get(student[0], "<b>Новая информация!</b>:\n")
                    a+=f"Оценка по <i>{GetShortcutText(subject_shr)}</i> <b><u>{extra}</u></b> от {date} была удалена!"
            elif (event_type == 'group_added'):
                cursor.execute("SELECT tid FROM students WHERE school = ? AND student_id = ?", (school, student_id))
                for j in cursor.fetchall():
                    a = msgs.get(j[0], "<b>Новая информация!</b>:\n")
                    a+=f"У вас сменилась группа по {GetShortcutText(subject_shr)}\nТеперь вы в группе <i>{extra}</i>\n"
                    msgs[j[0]] = a
                pass
            elif (event_type == 'log_out'):
                try:
                    await application.bot.send_message(student_id, f"Внимание, вас выбросило из профиля!\n<blockquote>Школа: {school}\nКласс: {class_name}\nПричина: <b>{extra}</b></blockquote>", parse_mode='HTML',reply_markup=DEV_RPMK,disable_web_page_preview=True)
                    time.sleep(1)
                except Exception as e:
                    print(f"Sending failed: {e}")
            elif (event_type == 'student_deleted'):
                try: 
                    await application.bot.send_message(chat_id=student_id, text=f"Вы были удалены из журнала!\n<blockquote>Школа: {school}\nКласс: {class_name}</blockquote>\nЕсли вы покинули ваш класс, то удачи вам)\nЕсли считаете это ошибкой, сообщиете разработчику", reply_markup=DEV_CLOSE_RPMK)
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Sending failed: {e}")
                
        except Exception as e:
            print(f"Error processing event: {e}")
            time.sleep(4)
    for k,v in msgs.items():
        try:
            await application.bot.send_message(k, v, parse_mode='HTML', reply_markup=DEV_CLOSE_RPMK)
        except Exception as e:
            print(f"SEND MSG EX: {e}")
        time.sleep(0.2)
    cursor.execute(f"DELETE FROM events WHERE id IN ({','.join([f"{i[0]}" for i in events])})")

async def PostProcessLesson(website, login, password, school, class_name, journal_id, lesson_id):
    print(f"started files proc for: {class_name} - {datetime.now().strftime("%Y-%m-%d %H:%M")}")
    time.sleep(1.5)
    d = GetOrCreateDnevnik(website, login, password)
    lesson:dict = d.GetLessonInfo(journal_id, lesson_id)
    if(lesson.get('errorno') is not None): 
        print('\tlesson not found!')
        return
    files = lesson['files']
    #print('Post processing files....')
    if(len(files) == 0): 
        print('\tNo files found!')
        return
    print("\tDetected files, starting downloading...")
    for i in files:
        file_id = i['id']
        file_name:str = i['name']
        cursor.execute("SELECT id FROM files WHERE school = ? AND file_id = ? AND file IS NOT NULL", (school, file_id))
        if(cursor.fetchone()): continue
        cursor.execute("INSERT OR IGNORE INTO files (school, lesson_id, file_id, file_name) VALUES (?, ?, ?, ?)", (school, lesson_id, file_id, file_name))
        off = file_name.rfind('.')
        file_name = f"files/{uuid.uuid4()}{file_name[off:]}"
        bts = d.DownloadFile(lesson_id, file_id)
        sh1 = hashlib.sha1(bts).hexdigest()
        cursor.execute("SELECT file FROM files WHERE hashsum = ?", (sh1,))
        file_al = cursor.fetchone()
        if(file_al):
            file_name = file_al[0]
        else:
            with open(file_name, 'wb') as f:
                f.write(bts)
        cursor.execute("UPDATE files SET file = ?, hashsum = ? WHERE school = ? AND file_id = ?", (file_name, sh1, school, file_id))

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

application = ApplicationBuilder().token(BOT_TOKEN).build()

asyncio.run(mainLoop())


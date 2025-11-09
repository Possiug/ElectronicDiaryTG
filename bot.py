from telegram import Update, Message, InlineKeyboardMarkup, InlineKeyboardButton, User, LabeledPrice, SuccessfulPayment, InputMediaPhoto, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, KeyboardButtonRequestUsers, LinkPreviewOptions, ChatMemberUpdated, ChatMember, Chat, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ExtBot, CallbackQueryHandler, PreCheckoutQueryHandler, ShippingQueryHandler, ChatMemberHandler
import sqlite3
from dnevnik import Dnevnik
from dnevnik_types import *
import string
import threading
import random
import urllib.parse
import hashlib
import asyncio
import os
import uuid
import re as RegExp
import time
from datetime import datetime, timedelta
from html import escape as HTMLescape
from dotenv import load_dotenv 

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PASSWORD = os.getenv("PASSWORD")
DB_FILENAME = 'ed.db'


connection = sqlite3.connect(DB_FILENAME, check_same_thread=False)
cursor = connection.cursor()


class UStates:
    AWAIT_OO_NUMBER_TEACHER = "aw_oo_num_t"
    AWAIT_OO_NAME_TEACHER = "aw_oo_name_t"
    AWAIT_OO_WEBSITE_T = "aw_oo_web_t"
    AWAIT_OO_CONFIRM_T = "aw_oo_confirm_t"
    AWAIT_FINAL_CONFIRM_T = "aw_f_confirm_t"
    AWAIT_LOGIN_T = "aw_log_t"
    AWAIT_PASS_T = "aw_pass_t"
    AWAIT_CHOOSE_ROLE = "aw_choose_role"
    AWAIT_ADMIN_PASS = "aw_admin_pass"
    AWAIT_EDIT_WEB_T = "aw_edit_web_t"
    AWAIT_EDIT_LP_T = "aw_edit_lp_t"
    UNKNOWN = "unknown"


users_state:dict[int, str] = {}
users_data:dict[int, dict] = {}
dnevniks:dict[str, Dnevnik] = {}
journals:dict[str, ]
lesson_types: dict[str, dict[str, str]] = {}
mark_types: dict[str, dict[str, str]] = {}
control_types: dict[str, dict[str, str]] = {}
change_reasons: dict[str, dict[str, str]] = {}
last_update = {'start': 0, 'stop': 0}
time_to_sleep = 0


def PrepareDB():
    cursor.execute('''CREATE TABLE IF NOT EXISTS schools (
                number INTEGER UNIQUE,
                name TEXT NOT NULL,
                website TEXT NOT NULL
                )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS dnevniks (
                id INTEGER PRIMARY KEY,
                school INTEGER NOT NULL,
                website TEXT NOT NULL,
                class_name TEXT NOT NULL,
                login TEXT NOT NULL,
                password TEXT NOT NULL,
                teacher_tid INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1
                )''')
   
    cursor.execute('''CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                school INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                invite_code INTEGER UNIQUE,
                status TEXT DEFAULT "invite",
                alias TEXT NOT NULL,
                tid INTEGER DEFAULT 0
                )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS class_linking (
                school INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                subject_shr INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                UNIQUE (school, student_id, subject_shr)
                )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS lessons (
                school INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                id INTEGER NOT NULL,
                type_shr INTEGER NOT NULL,
                subject_shr INTEGER NOT NULL,
                num INTEGER NOT NULL,
                homework INTEGER DEFAULT "",
                date DATE CURRENT_DATE,
                updated_date DATE CURRENT_DATE,
                UNIQUE (school, id)
                )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS shortcuts (
                id INTEGER PRIMARY KEY,
                text TEXT UNIQUE
                );''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS marks (
                school INTEGER NOT NULL,
                mark_id INTEGER NOT NULL,
                mark_char TEXT NOT NULL,
                shortname TEXT NOT NULL,
                subject_shr INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                value REAL NOT NULL,
                cost REAL NOT NULL,
                text TEXT DEFAULT "",
                date DATE CURRENT_DATE,
                UNIQUE (school, mark_id)
                );''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS periods (
                school INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                date_from DATE NOT NULL,
                date_to DATE NOT NULL,
                number INTEGER NOT NULL,
                UNIQUE (school, class_name, number)
                );''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                school INTEGER NOT NULL,
                lesson_id INTEGER NOT NULL,
                file_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file TEXT,
                hashsum TEXT,
                date DATE DEFAULT CURRENT_DATE,
                UNIQUE (school, file_id)
                );''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL,
                school INTEGER DEFAULT -1,
                class TEXT DEFAULT "-1xyz",
                subject_shr INTEGER DEFAULT -1,
                student_id INTEGER DEFAULT -1,
                lesson_id INTEGER DEFAULT -1,
                mark_id INTEGER DEFAULT -1,
                extra TEXT DEFAULT "",
                affected_date DATE DEFAULT CURRENT_DATE,
                date DATE CURRENT_DATE
                );''')
    cursor.execute('''CREATE TRIGGER IF NOT EXISTS delete_student
                   AFTER DELETE ON students
                   BEGIN
                       DELETE FROM class_linking WHERE school = OLD.school AND student_id = OLD.student_id;
                       DELETE FROM marks WHERE school = OLD.school AND student_id = OLD.student_id;
                       INSERT INTO events (type, school, student_id, class) VALUES 
                       ("student_deleted", OLD.school, OLD.tid, OLD.class_name);
                   END;''')
    cursor.execute('''CREATE TRIGGER IF NOT EXISTS new_lesson 
                AFTER INSERT ON lessons
                BEGIN
                   INSERT INTO events (type, school, class, subject_shr, lesson_id, extra, affected_date) VALUES 
                   ("lesson_added", NEW.school, NEW.class_name, NEW.subject_shr, NEW.id, NEW.homework, NEW.date);
                END;''')
    cursor.execute('''CREATE TRIGGER IF NOT EXISTS new_mark
                AFTER INSERT ON marks
                BEGIN
                   INSERT INTO events (type, school, subject_shr, mark_id, student_id, extra, affected_date) VALUES 
                   ("mark_added", NEW.school, NEW.subject_shr, NEW.mark_id, NEW.student_id, NEW.shortname, NEW.date);
                END;''')
    cursor.execute('''CREATE TRIGGER IF NOT EXISTS delete_mark
                AFTER DELETE ON marks
                BEGIN
                   INSERT INTO events (type, school, subject_shr, mark_id, student_id, extra, affected_date) VALUES 
                   ("mark_deleted", OLD.school, OLD.subject_shr, OLD.mark_id, OLD.student_id, OLD.mark_char, OLD.date);
                END;''')
    cursor.execute('''CREATE TRIGGER IF NOT EXISTS new_group_lnk 
                AFTER INSERT ON class_linking
                BEGIN
                   DELETE FROM class_linking WHERE school = NEW.school AND student_id = NEW.student_id AND subject_shr = NEW.subject_shr AND group_name != NEW.group_name ;
                   INSERT INTO events (type, school, class, subject_shr, student_id, extra) VALUES 
                   ("group_added", NEW.school, NEW.class_name, NEW.subject_shr, NEW.student_id, NEW.group_name);
                END;''')
    cursor.execute('''VACUUM;''')

    

    connection.autocommit = True






#region RPMKs
ROLES_RPMK = ReplyKeyboardMarkup([[KeyboardButton("Учитель")], [KeyboardButton("Ученик")]], one_time_keyboard=True, resize_keyboard=True)
ADMIN_RPMK = InlineKeyboardMarkup([[InlineKeyboardButton("Тест", callback_data="test")]])
DEV_BUTTON = [InlineKeyboardButton(text="К разработчику", url="t.me/possiug")]
DEV_RPMK = InlineKeyboardMarkup([DEV_BUTTON])
CLOSE_BUTTON = [InlineKeyboardButton(f"Закрыть", callback_data="delete_me")]
CLOSE_RPMK = InlineKeyboardMarkup([CLOSE_BUTTON])
CANCEL_BUTTON = [InlineKeyboardButton(f"Отмена", callback_data="cancel_me")]
CANCEL_RPMK = InlineKeyboardMarkup([CANCEL_BUTTON])
DEV_CLOSE_RPMK = InlineKeyboardMarkup([DEV_BUTTON, CLOSE_BUTTON])

#endregion


#region Async Utils

async def mainLoop():
    global time_to_sleep
    while True:
        time_to_sleep = 60*60
        while time_to_sleep > 0:
            current_h = datetime.now().hour
            print(time_to_sleep)
            if(current_h > 23 or current_h < 5):
                await asyncio.sleep(1)
            await asyncio.sleep(1)
            time_to_sleep -= 1
            if not (is_active): 
                print("main loop falling down")
                exit()
            if(time_to_sleep%10 == 0):  
                try:
                    await EventProc()
                except: pass
        await UpdateData()
async def UpdateData():
    cursor.execute("SELECT id, school, class_name, website, login, password, teacher_tid FROM dnevniks WHERE is_active = 1")
    sql_answer = cursor.fetchall()
    last_update["start"] = time.time()
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
                    if (pcount != len(periods)):
                        for n, i in enumerate(periods, start=1):
                            cursor.execute("INSERT OR IGNORE INTO periods (school, class_name, date_from, date_to, number) VALUES (?, ?, ?, ?, ?)", 
                                           (school, class_name, i['date_from'], i['date_to'], n))
                    excluded = set()
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
                    

                    lessons:list[dict] = data['lessons']
                    lsndate = {}
                    for i in lessons:
                        lesson_id:str = i['id']
                        lsndate[lesson_id] = i['date']
                        sus = i['lt'] # check for final lesson and V-type lesson
                        if (sus != ''):
                            print('skipping')
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
                    marks = data['marks']
                    real_marks = set()
                    cursor.execute("SELECT mark_id FROM marks WHERE school = ? AND subject_shr = ? AND student_id IN (SELECT student_id FROM students WHERE school = ? AND class_name = ? UNION SELECT student_id FROM class_linking WHERE school = ? AND group_name = ? AND subject_shr = ?)", 
                                   (school, subject_shr, school, k, school, k, subject_shr)
                                   )
                    phantom_marks:set[int] = set([i[0] for i in cursor.fetchall()])
                    mark_type_cache = {}
                    
                    for i in data['mark_types']:
                        for j in i['marks']:
                            mark_type_cache[j['id']] = {
                                'name': j['name'],
                                'shortname': j['shortname'],
                                'cost': float(j['cost']),
                                'key': j['key']
                            }
                    for i in marks:
                        m_id:str = i['id'] 
                        if (i['student_id'] in excluded): continue
                        real_marks.add(int(m_id))
                        if (int(m_id) in phantom_marks): continue
                        control_id:str = i['control_id']
                        control = ctrls[control_id]
                        key = mark_type_cache.get(i['type_id'])
                        typ = None
                        if (control_id.startswith('f')):
                            typ = {
                                'shortname': control['short'],
                                'cost': control['cost']
                            }
                            i['text'] = 'pSS:f1nAl'
                        else:
                            typ = GetTypeFromId(control['type_id'], data['control_types'])
                        cursor.execute("INSERT OR IGNORE INTO marks (school, mark_id, mark_char, shortname, subject_shr, student_id, value, cost, text, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (school, m_id, key['key'], typ['shortname'], subject_shr, i['student_id'], float(key['cost']), float(typ['cost']), i['text'], lsndate[control['lesson_id']])
                                    )
                        
                    print(len(phantom_marks))
                    print(len(real_marks))
                    for i in phantom_marks:
                        if not i in real_marks:
                            print(f"deleting {i}")
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
            event_type = i[1]
            school = i[2]
            class_name = i[3]
            subject_shr = i[4]
            student_id = i[5]
            lesson_id = i[6]
            mark_id = i[7]
            extra = i[8]
            date = i[9]
            print(f"Processing {event_type} event: {i}")
            if (event_type == 'lesson_added'):
                cursor.execute("SELECT tid FROM students WHERE tid != 0 AND school = ? AND (class_name = ? OR student_id IN (SELECT student_id FROM class_linking WHERE school = ? AND subject_shr = ? AND group_name = ?))", (school, class_name, school, subject_shr, class_name))
                students = cursor.fetchall()
                for j in students:
                    a = msgs.get(j[0], "<b>Новая информация!</b>:\n")
                    a+=f"Новое дз по <i>{GetShortcutText(subject_shr)}</i> от {date}:\n<blockquote expandable>{extra}</blockquote>\n"
                    msgs[j[0]] = a
            elif (event_type == 'mark_added'):
                cursor.execute("SELECT tid FROM students WHERE school = ? AND student_id = ? AND tid != 0", (school, student_id, ))
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
                cursor.execute("SELECT tid FROM students WHERE school = ? AND student_id = ? AND tid != 0", (school, student_id, ))
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
    if(lesson.get('errorno') != None): 
        print('lesson not found!')
        return
    files = lesson['files']
    #print('Post processing files....')
    if(len(files) == 0): 
        print('No files found!')
        return
    print("Detected files, starting downloading...")
    for i in files:
        file_id = i['id']
        file_name:str = i['name']
        cursor.execute("SELECT id FROM files WHERE school = ? AND file_id = ? AND file IS NOT NULL", (school, file_id))
        if(cursor.fetchone()): continue
        cursor.execute("INSERT INTO files (school, lesson_id, file_id, file_name) VALUES (?, ?, ?, ?)", (school, lesson_id, file_id, file_name))
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


async def SendLongMsg(bot:ExtBot, chatid:int, text:str, reply_to:int|None = None):
    if len(text)>4096:
        for i in range(len(text)//4096+1):
            await bot.send_message(chat_id=chatid, text=text[i*4096:(i+1)*4096], reply_to_message_id=reply_to, parse_mode='HTML')
    else:       
        return await bot.send_message(chat_id=chatid, text=text, reply_to_message_id=reply_to, parse_mode='HTML')


async def StartCommandProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    sender = update.effective_sender
    args = context.args
    code = args[0][1:]
    
    if(code.startswith("file")):
        file_hash = code[4:]
        cursor.execute("SELECT file, file_name FROM files WHERE hashsum = ?", (file_hash,))
        file = cursor.fetchone()
        if(file == None):
            await msg.reply_html(f"Файл не найден!",reply_markup=DEV_CLOSE_RPMK)
            return
        await chat.send_document(InputFile(open(file[0], 'rb').read(), filename=file[1]), caption=f"Файл", write_timeout=30, read_timeout= 30)
    elif(code.startswith("pea")):
        student_code = code[3:]
        cursor.execute("SELECT id, alias, school, class_name, status FROM students WHERE invite_code = ?", (student_code,))
        student = cursor.fetchone()
        if(student == None):
            await msg.reply_html(f"Ученик не найден!",reply_markup=DEV_CLOSE_RPMK)
            return
        cursor.execute("SELECT id FROM dnevniks WHERE teacher_tid = ? AND school = ? AND class_name = ?", (sender.id, student[2], student[3]))
        journal = cursor.fetchone()
        if(journal == None):
            await msg.reply_html(f"Кажется вы не учитель этого ученика!!",reply_markup=CLOSE_RPMK)
            return
        is_loggedin = student[4] == "student"
        buttons = []
        if(is_loggedin):
            buttons.append([InlineKeyboardButton("Завершить сессию", callback_data=f"kick_t:{journal[0]}:{student[0]}")])
        else:
            buttons.append([InlineKeyboardButton("Сменить ссылку", callback_data=f"regenlink_t:{journal[0]}:{student[0]}")])
        buttons.append([InlineKeyboardButton("Удалить ученика", callback_data=f"predelete_student:{journal[0]}:{student[0]}")])
        buttons.append([InlineKeyboardButton("Отправить ссылку", url=f"https://t.me/share/url?url={urllib.parse.quote_plus(f"{student[1]}, присоединяйтесь к ЭД: {GetInviteLink(student_code)}")}")])
        buttons.append(CLOSE_BUTTON)

        await msg.reply_html(f"<blockquote>Школа: {student[2]}\nКласс: {student[3]}\nФамилия имя: {student[1]}\nСтатус: {"войден" if is_loggedin else "приглашен"}</blockquote>\nСсылка-приглашение: <code>{GetInviteLink(code)}</code>\n\n<b>Выберите действие:</b>", reply_markup=InlineKeyboardMarkup(buttons))
    elif(code.startswith("hws")):
        subject_shr = code[3:]
        cursor.execute("SELECT student_id, school, class_name FROM students WHERE tid = ?", (sender.id,))
        student = cursor.fetchone()
        if(student == None):
            await msg.reply_html(f"Вы не вошли в аккаунт, используйте /menu чтобы получить больше информации",reply_markup=CLOSE_RPMK)
            return
        text = "<u>За последние 2 недели</u>:\n"+GetHTMLSubjectHomework(student[1], student[2], subject_shr, student[0], 100, 14, 14)
        await chat.send_message(text, parse_mode='HTML', reply_markup=CLOSE_RPMK, disable_web_page_preview=True)
    elif(code.startswith("mrks")):
        subject_shr = code[4:]
        cursor.execute("SELECT student_id, school, class_name FROM students WHERE tid = ?", (sender.id,))
        student = cursor.fetchone()
        if(student == None):
            await msg.reply_html(f"Вы не вошли в аккаунт, используйте /menu чтобы получить больше информации",reply_markup=CLOSE_RPMK)
            return
        
        await chat.send_message(GetSubjectMarks(student[0], student[1], student[2], subject_shr), parse_mode='HTML', reply_markup=CLOSE_RPMK, disable_web_page_preview=True)
    elif(code.startswith("mtd")):
        date_from = code[3:13]
        date_to = code[13:23]
        subject_shr = code[23:]
        cursor.execute("SELECT student_id, school, class_name FROM students WHERE tid = ?", (sender.id,))
        student = cursor.fetchone()
        if(student == None):
            await msg.reply_html(f"Вы не вошли в аккаунт, используйте /menu чтобы получить больше информации",reply_markup=CLOSE_RPMK)
            return
        
        await chat.send_message(GetSubjectMarks(student[0], student[1], student[2], subject_shr, date_from, date_to), parse_mode='HTML', reply_markup=CLOSE_RPMK, disable_web_page_preview=True)
    await msg.delete()


#endregion


#region Sync Utils



def RandomWord(length):
   c = string.ascii_letters + string.digits
   return ''.join(random.choice(c) for i in range(length))

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

def GetOrCreateDnevnikfromUD(ud:dict) -> Dnevnik:
    return GetOrCreateDnevnik(ud['school_web'], ud["login"], ud['password'])

def GenerateDID(website, login, password) -> str:
    return hashlib.md5(f"{website}!{login}~{password}".encode('utf-8')).hexdigest()

def GenerateDIDfromUserdata(ud:dict):
    return GenerateDID(ud['school_web'], ud["login"], ud['password'])

def GetStudentCode(k):
    return hashlib.md5(f"{k}{RandomWord(5)}".encode('utf-8')).hexdigest()

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

def GetStartLink(arg:str) -> str:
    return f"t.me/pss_ednevnik_bot?start={arg}"

def GetInviteLink(code:str) -> str:
    return GetStartLink(f"ycode{code}")

def GetFullHomework(student_id, school, class_name):
    cursor.execute("SELECT DISTINCT subject_shr FROM lessons WHERE school = ? AND class_name IN (SELECT group_name FROM class_linking WHERE student_id = ? UNION SELECT ?)", (school, student_id, class_name))
    sbjcs = cursor.fetchall()
    count = 3
    while count >= 1:
        text = "Домашние задания:\n"
        for i in sbjcs:
            text+=GetHTMLSubjectHomework(school, class_name, i[0], student_id, count)
        if(len(text) > 4096):
            count -= 1
            continue
        return text
    raise RuntimeError("Очень странно, но дз не вмещается в одно сообщение, а разработчик не придумал что с этим делать")

def GetCurrentTermBound(school:int, class_name:str) -> tuple[str, str]:
    cursor.execute("SELECT date_from FROM periods WHERE school = ? AND class_name = ? AND date_from <= date('now') ORDER BY date_from DESC LIMIT 1", (school, class_name))
    date_from = cursor.fetchone()
    if (date_from is None):
        date_from = datetime(datetime.now().year, 0, 0).strftime("%Y-%m-%d")
    else:
        date_from = date_from[0]
    cursor.execute("SELECT date_from FROM periods WHERE school = ? AND class_name = ? AND date_from >= date('now') ORDER BY date_from ASC LIMIT 1", (school, class_name))
    date_to = cursor.fetchone()
    if (date_to is None):
        date_to = datetime.now().strftime("%Y-%m-%d")
    else:
        date_to = date_to[0]
    return date_from, date_to
    
def GetSubjectMarks(student_id, school, class_name, subject_shr, date_from = None, date_to = None) -> str:
    if (date_from is None or date_to is None):
        ndate_from, ndate_to = GetCurrentTermBound(school, class_name)
        if (date_to is None):
            date_to = ndate_to
        if (date_from is None):
            date_from = ndate_from
    cursor.execute("SELECT mark_char, shortname, value, cost, text, date FROM marks WHERE student_id = ? AND text != 'pSS:f1nAl' AND subject_shr = ? AND date BETWEEN ? AND ?", (student_id, subject_shr, date_from, date_to))
    marks = cursor.fetchall()
    text = f"<i>Период: {date_from} {HTMLescape('->')} {date_to}</i>\nОценки по {GetShortcutText(subject_shr)}:\n"
    m_sum = 0
    m_count = 0
    for i in marks:
        text += f"{i[5]} - <b>{i[0]}</b>{f"({i[4]})" if i[4] else ""} - {i[1]} - кофф: {i[3]}\n"
        if(i[2] != 0):
            m_sum += i[2] * i[3]
            m_count += i[3]
    if(m_count != 0):
        text += f"\n<i>Средний балл: {m_sum/m_count:.2f}</i>"
    return text

def GetFullMarks(student_id, school, class_name, date_from = None, date_to = None) -> str:
    m_sum = 0
    m_count = 0
    term_depended = False
    if (date_from is None or date_to is None):
        ndate_from, ndate_to = GetCurrentTermBound(school, class_name)
        if (date_to is None):
            date_to = ndate_to
        if (date_from is None):
            date_from = ndate_from
    else:
        term_depended = True
    text = f"<i>Оценки за период: {date_from} {HTMLescape("->")} {date_to}</i>\n"
    cursor.execute("SELECT DISTINCT subject_shr FROM lessons WHERE school = ? AND class_name IN (SELECT group_name FROM class_linking WHERE student_id = ? UNION SELECT ?)", (school, student_id, class_name))
    for i in cursor.fetchall():
        cursor.execute("SELECT mark_char, text, value, cost FROM marks WHERE student_id = ? AND text != 'pSS:f1nAl' AND subject_shr = ? AND date BETWEEN ? AND ? ORDER BY date ASC", (student_id, i[0], date_from, date_to))
        sql_answer = cursor.fetchall()
        link = GetStartLink(f"qmrks{i[0]}")
        if (term_depended):
            link = GetStartLink(f"qmtd{date_from}{date_to}{i[0]}")
        text+=f"<b><a href=\"{link}\">{GetShortcutText(i[0])}</a></b>: "
        
        text += ', '.join([f"{j}{f" ({k})" if k != "" else ""}" for j,k,*q in sql_answer])
        text += "\n"
        for j in sql_answer:
            if(j[2] != 0):
                m_sum += j[2] * j[3]
                m_count += j[3]
    if(m_count != 0):
        text+=f"\n\n<i>Средний балл: {m_sum/m_count:.2f}</i>"
    return text


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

def GetHTMLSubjectHomework(school, class_name, subject_shr, student_id, limit = 3, day_offset = 7, days = 7):
    text = ""
    cursor.execute("SELECT date('now', ?), date('now', ?)", (f'{-day_offset} days', f'{days-day_offset} days'))
    data = cursor.fetchone()
    start_date, stop_date = data[0], data[1]    
    cursor.execute("SELECT homework, date, id FROM lessons WHERE school = ? AND subject_shr = ? AND date >= ? AND date <= ? AND class_name IN (SELECT group_name FROM class_linking WHERE student_id = ? AND subject_shr = ? UNION SELECT ?) ORDER BY date DESC, num DESC LIMIT ?", (school, subject_shr, start_date, stop_date, student_id, subject_shr, class_name, limit))
    sql_answer = cursor.fetchall()
    text+=f"<a href=\"{GetStartLink(f"qhws{subject_shr}")}\"><b>{GetShortcutText(subject_shr)}:</b></a>\n<blockquote expandable>"
    for j in sql_answer:
        cursor.execute("SELECT hashsum, file_name FROM files WHERE school = ? AND lesson_id = ?", (school, j[2]))
        files = cursor.fetchall()
        files_txt = f"    Файлы: {', '.join([f"<a href=\"t.me/pss_ednevnik_bot?start=qfile{k[0]}\">{k[1]}</a>" for k in files])}\n"
        text+=f"<b>{j[1]}</b>: {j[0]}\n{files_txt if len(files) != 0 else ""}"
    text+="</blockquote>\n"
    return text




#endregion




async def StartProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    sender = update.effective_sender
    args = context.args
    if(len(args) != 0):    
        code = args[0]
        if(code.startswith('q')):
            await StartCommandProc(update, context)
            return
        if(code.startswith('ycode')):
            code = code[5:]
            cursor.execute("SELECT school, class_name, alias FROM students WHERE tid = ?", (sender.id,))
            already = cursor.fetchone()
            if(already != None):
                await msg.reply_html(f"Вы уже привязаны к электронному дневнику!\nСначала выдите из профиля!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выйти",callback_data='logout_s')], CLOSE_BUTTON]))
                return
            cursor.execute("SELECT school, class_name, alias FROM students WHERE invite_code = ?", (code,))
            invite = cursor.fetchone()
            if(invite == None):
                await msg.reply_html("Кажется ваша ссылка приглашения недействительна!\nПопросите учителя создать новую или обратитесь к разработчику", reply_markup=DEV_RPMK)
                return
            await msg.reply_html(f"Добро пожаловать!<blockquote>Школа: {invite[0]}\nКласс: {invite[1]}\nФамилия имя: {invite[2]}</blockquote>\nЭто вы?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Да",callback_data=f"its_me_s:{code}")], [InlineKeyboardButton("Нет", callback_data="itsnt_me_s")]]))
        return
    await msg.reply_html("Добро пожаловать в бота!\nБот предоставляет доступ к вашим оценкам и дз без госуслуг и сложной авторизации, прямо в телеграмме\nЧтобы начать, выберите свою роль:",reply_markup=ROLES_RPMK)
async def ProfileProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    sender = update.effective_sender
    cursor.execute("SELECT id, student_id, school, class_name, alias FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    if(student == None):
        await msg.reply_html(f"Вы еще не привязаны к электронному дневнику! Попросите у вашего учителя ссылку для привязки!", reply_markup=CLOSE_RPMK)
        return
    await msg.reply_html(f"Ученик:<blockquote>Школа: {student[2]}\nКласс: {student[3]}\nФамилия имя: {student[4]}</blockquote>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Обновить имя",callback_data=f"update_fio_s")], [InlineKeyboardButton("Выйти",callback_data="logout_s")], CLOSE_BUTTON]))
    
async def StatusProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    sender = update.effective_sender
    cursor.execute("SELECT school, class_name, alias FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    text = f"Статус:\n<blockquote>Обновление старт: {datetime.fromtimestamp(last_update['start'])}\n          завершение: {datetime.fromtimestamp(last_update['stop'])}\nОбновление через: {time_to_sleep} сек."
    if(student):
        cursor.execute("SELECT is_active FROM dnevniks WHERE class_name = ? AND school = ?", (student[1], student[0]))
        dnev = cursor.fetchone()
        text +=f"\nУченик: {student[2]}"
        if(dnev):
            text+=f"\nДневник: {"активен" if dnev[0] else "НЕАКТИВЕН"}"
    text += "</blockquote>"
    await msg.reply_html(text)


async def HomeWorkCMDProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    sender = update.effective_sender
    cursor.execute("SELECT student_id, school, class_name FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    if(student == None):
        await msg.reply_html(f"Вы еще не привязаны к электронному дневнику! Попросите у вашего учителя ссылку для привязки!", reply_markup=CLOSE_RPMK)
        return
    await chat.send_message(GetFullHomework(*student), parse_mode='HTML', disable_web_page_preview=True, reply_markup=CLOSE_RPMK)

async def MarksCMDProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    sender = update.effective_sender
    cursor.execute("SELECT student_id, school, class_name FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    if(student == None):
        await msg.reply_html(f"Вы еще не привязаны к электронному дневнику! Попросите у вашего учителя ссылку для привязки!", reply_markup=CLOSE_RPMK)
        return
    await chat.send_message(GetFullMarks(*student), parse_mode='HTML', disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="Другие периоды", callback_data="show_choose_term_s")], CLOSE_BUTTON]))


async def MsgProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global users_data
    global users_state
    msg = update.effective_message
    chat = update.effective_chat
    sender = update.effective_sender
    if (sender == None): return
    state = users_state.get(sender.id, UStates.UNKNOWN)
    if(msg.text == None): return
    mText = msg.text.lower()
    users_data[sender.id] = users_data.get(sender.id, {})
    user_d = users_data[sender.id]
    if(state == UStates.UNKNOWN):
        await msg.reply_html(f"Здравствуйте, чтобы начать работу в боте для электронного дневника, выберите вашу роль:", reply_markup=ROLES_RPMK)
        users_state[sender.id] = UStates.AWAIT_CHOOSE_ROLE
        return
    if(state == UStates.AWAIT_CHOOSE_ROLE):
        if(mText == "учитель"):
            cursor.execute("SELECT school, class_name FROM dnevniks WHERE teacher_tid = ?", (sender.id,))
            sql_answer = cursor.fetchall()
            if len(sql_answer) > 0:
                t = ""
                for i in sql_answer:
                    t+=f"{i[0]} - {i[1]}\n"
                await msg.reply_html(f"Вы уже учитель следущих классов:<blockquote>{t}</blockquote>\nВыберите действие:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Изменит/удалить ЭД", callback_data="edit_journals_t:0")], [InlineKeyboardButton("Добавить новый ЭД",callback_data="start_teacher")]]))
                return
            await msg.reply_html(f"Если Вы являетесь <b>УЧИТЕЛЕМ</b>, то, чтобы сделать электронный дневник для вашего класс без госуслуг, вам необходимо ввести <u><b>номер вашей школы</b></u>(Только номер: без ГБОУ, ФМЛ и тд.):")
            users_state[sender.id] = UStates.AWAIT_OO_NUMBER_TEACHER
        elif(mText == "ученик"):
            cursor.execute("SELECT * FROM students WHERE tid = ?", (sender.id, ))
            if (cursor.fetchone() != None):
                await ProfileProc(update, context)
                return
            await msg.reply_html(f"Если Вы являетесь <b>УЧЕНИКОМ</b>, то, чтобы смотреть оценки прямо в тг без госуслуг и получать уведомления о дз и оценках, вам необходимо получить уникальную сслыку от вашего учителя для входа в профиль, попросите учителя отправить сслыку, сгенерированную этим ботом!")
            users_state[sender.id] = UStates.UNKNOWN
        else:
            await msg.reply_html("Неизвестная роль! Выберите свою роль, чтобы начать:", reply_markup=ROLES_RPMK)
            users_state[sender.id] = UStates.AWAIT_CHOOSE_ROLE
        return
    elif(state == UStates.AWAIT_OO_NUMBER_TEACHER):
        if(not RegExp.fullmatch("\\d+", mText)):
            await msg.reply_html(f"Ожидается номер ОУ, вы ввели не номер! Попробуйте еще раз")
            return
        number = int(mText)
        user_d['school_num'] = number
        cursor.execute("SELECT name, website FROM schools WHERE number = ?", (number,))
        school = cursor.fetchone()
        if(school == None):
            user_d['is_new_school'] = True
            await msg.reply_html(f"Кажется вы первый кто регистрируется из этой школы, <u><b>введите полное наименование ОУ</b></u> (можно с сокращениями, это просто отображаемое имя):")
            users_state[sender.id] = UStates.AWAIT_OO_NAME_TEACHER
        else:
            await msg.reply_html(f"Отлично, ваша школа {number}:\n   Полное наименование ОУ: <code>{HTMLescape(school[0])}</code>\n   Вебсайт: {school[1]}\n\nЕсли данные не совпадают, сообщите разработчику\nДанные верные?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Да", callback_data="te_log_pass")], DEV_BUTTON]))
            user_d['school_name'] = msg.text
            user_d['school_web'] = school[1]
            users_state[sender.id] = UStates.AWAIT_OO_CONFIRM_T
        #users_state[sender.id] = UStates.UNKNOWN
    elif(state == UStates.AWAIT_OO_NAME_TEACHER):
        user_d['school_name'] = msg.text
        await msg.reply_html(f"Продолжаем регистрировать вашу школу, введите <u><b>внешний веб адрес системы Параграф</b></u> (тот в котором вы можете ставить оценки из дома), просьба вводить без https:// или http:// :")
        users_state[sender.id] = UStates.AWAIT_OO_WEBSITE_T
    elif(state == UStates.AWAIT_OO_WEBSITE_T):
        web_site = msg.text.replace('http://', '').replace('https://', '').replace('/', '')
        if(not RegExp.match("[0-9a-bA-BА-Яа-яЁё.]*.[a-bA-BА-Яа-яЁё.]*", web_site)):
            await msg.reply_html(f"Введен некоректный веб адресс, попробуйте еще раз, вводите адрес без приставок https:// и http:// а так же без / на конце!\nВведите веб адрес системы Параграф:")
            return
        user_d['school_web'] = web_site
        await msg.reply_html('Теперь перейдем к регистрации вас, введите ваш <u><b>логин в системе Параграф</b></u>:')
        users_state[sender.id] = UStates.AWAIT_LOGIN_T
    elif(state == UStates.AWAIT_EDIT_WEB_T):
        web_site = msg.text.replace('http://', '').replace('https://', '').replace('/', '')
        if(not RegExp.match("[0-9a-bA-BА-Яа-яЁё.]*.[a-bA-BА-Яа-яЁё.]*", web_site)):
            await msg.reply_html(f"Введен некоректный веб адресс, попробуйте еще раз, вводите адрес без приставок https:// и http:// а так же без / на конце!\nВведите веб адрес системы Параграф:")
            return
        m = await msg.reply_html(f"Проверка данных перед внесения изменений...\nЭто может занять некоторое время...")
        try:
            Dnevnik(web_site)
        except Exception as e:
            print(f"Error in new web: {e}")
            await m.edit_text(f"Не удалось установить соединение с сайтом!\nПроверьте адрес или обратитесь к разработчику!\n\nВведите <u><b>новый веб адрес журнала</b></u>:", parse_mode='HTML', reply_markup=InlineKeyboardButton(CANCEL_BUTTON, DEV_BUTTON))
            return
        cursor.execute("UPDATE dnevniks SET website = ? WHERE teacher_tid = ? AND id = ?", (web_site, sender.id, user_d['journal_id']))
        await msg.delete()
        await m.edit_text(f"Успешно установлен новый адрес журнала:\n{web_site}", reply_markup=CLOSE_RPMK)
        users_state[sender.id] = UStates.UNKNOWN
    elif(state == UStates.AWAIT_EDIT_LP_T):
        lp = msg.text.split('\n')
        if (len(lp) != 2): 
            await msg.reply_html(f"<b>Неверный формат!</b>\nВаше сообщение должно содержать 2 строки:\n 1) логин\n 2) пароль\n\nПопробуйте еще раз:", reply_markup=CANCEL_RPMK)
            return
        login = lp[0]
        password = lp[1]
        m = await msg.reply_html(f"Проверка данных перед внесения изменений...\nЭто может занять некоторое время...")
        cursor.execute("SELECT website FROM dnevniks WHERE id = ?", (user_d['journal_id'],))
        host = cursor.fetchone()[0]
        try:
            d = Dnevnik(host)
            d.Login(login, password)
        except LoginError:
            await m.edit_text(f"Не удалось войти с предоставленными данными\n\n<i>при возникновении трудностей, обратитесь к разработчику!</i>\n\nВведите <u><b>новый логин и пароль</b></u>:", parse_mode='HTML', reply_markup=InlineKeyboardButton(CANCEL_BUTTON, DEV_BUTTON))
            return
        except Exception as e:
            print(f"Error in new lp: {e}")
            await m.edit_text(f"Кажется сайт ЭД недоступен или произошла ошибка, попробуйте снова позже или сообщите разработчику\n\nВведите <u><b>новый логин и пароль</b></u>:", parse_mode='HTML', reply_markup=InlineKeyboardButton(CANCEL_BUTTON, DEV_BUTTON))
            return
        cursor.execute("UPDATE dnevniks SET login = ?, password = ? WHERE teacher_tid = ? AND id = ?", (login, password, sender.id, user_d['journal_id']))
        await msg.delete()
        await m.edit_text(f"Успешно установлен новык логин и пароль:\n<code>{login}:{password}</code>", reply_markup=CLOSE_RPMK)
        users_state[sender.id] = UStates.UNKNOWN
        
            
    elif(state == UStates.AWAIT_LOGIN_T):
        login = msg.text
        user_d['login'] = login
        await msg.reply_html(f"Введите ваш <u><b>пароль от системы Параграф</b></u>:")
        users_state[sender.id] = UStates.AWAIT_PASS_T
    elif(state == UStates.AWAIT_PASS_T):
        password = msg.text
        user_d['password'] = password
        await msg.reply_html(f"Итого:<blockquote>Вы учитель школы №{user_d['school_num']}\nПолное наименование ОУ: {user_d['school_name']}\nСайт Параграф: {user_d['school_web']}\nЛогин: {user_d['login']}\nПароль: {user_d['password']}</blockquote>\nВерно?",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Да, все верно", callback_data="all_ok_tr")], [InlineKeyboardButton("Исправить логин и пароль", callback_data="enter_login_t")], [InlineKeyboardButton("Начать заново", callback_data="menu")]]))
        users_state[sender.id] = UStates.AWAIT_FINAL_CONFIRM_T
    pass


async def MenuProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    sender = update.effective_sender
    await msg.reply_html(f"Меню. Выберите вашу роль:", reply_markup=ROLES_RPMK)
    users_state[sender.id] = UStates.AWAIT_CHOOSE_ROLE
    users_data[sender.id] = {}

async def AdminProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    sender = update.effective_sender
    data = msg.text.split('\n')
    if(context.args[0] == PASSWORD):
        r = "Результат:\n"
        k = 1
        for i in data[1:]:
            try:
                if(i == 'force update'): 
                    global time_to_sleep
                    time_to_sleep = 0
                    continue
                cursor.execute(i)
                sql = cursor.fetchall()
                data = ""
                j = 0
                for i in sql:
                    data += f"    {j}: {i}\n"
                    j+=1
                r+=f"{k}.\n{data}"
            except Exception as e:
                r += f"{k}. {e}\n"
            k+=1
        rpmk = InlineKeyboardMarkup([[InlineKeyboardButton(text="#TODO",callback_data="test")]])
        await chat.send_message(parse_mode="HTML", text="Добро пожаловать в админ панель\nБудьте потише здесь :)\n\n", reply_markup=rpmk)
        if(len(r) > 4096*4):
            await chat.send_message(parse_mode="HTML", text="Результат выполнения SQL слишком большой для отправки, вывожу в консоль...", reply_markup=rpmk)
            print(r)
        else:
            await SendLongMsg(context.bot, chat.id, r)



#region Callback Func

async def TestProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.reply_html(f"Тест успешен, аргументы: {args}")
async def DeleteMeProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.delete()
async def CancelMeProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    users_state[sender.id] = UStates.UNKNOWN
    await msg.delete()
async def Menu(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.reply_html(f"Меню. Выберите вашу роль:", reply_markup=ROLES_RPMK)
    users_state[sender.id] = UStates.AWAIT_CHOOSE_ROLE
    users_data[sender.id] = {}
async def AllDataConfirmedProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.edit_text(parse_mode="HTML", text="Производим проверку перед записью данных...\nЭто может занять некоторое время...",reply_markup=None)
    user_d = users_data.get(sender.id, None)
    if(user_d == None):
        await msg.edit_text(f"Произошла потеря данных, возможно бот был перезапущен, сожалеем, но придется перезаполнить данные использовав /menu")
        return
    parallels = None
    try:
        d = GetOrCreateDnevnikfromUD(user_d)
        parallels = d.GetParallels()
    except ConnectError:
        await msg.edit_text(f"Кажется вы неправильно указали адресс веб Портала, попробуйте перезаполнить данные или связаться с разработчиком (@possiug)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести адрес снова", callback_data="enter_web_t")], DEV_BUTTON]))
    except LoginError:
        await msg.edit_text(f"Неверный логин или пароль, введите его заного или обратитесь к разработчику (@possiug)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ввести логин снова", callback_data="enter_login_t")], DEV_BUTTON]))
    except Exception as e:
        print(e)
        await msg.edit_text(f"Произошла ошибка, возможно вы или предыдущие учителя неправильно указали адрес Веб Портала",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Попробовать снова",callback_data="all_ok_tr")], DEV_BUTTON, [InlineKeyboardButton("Изменить адрес", callback_data="enter_web_t")] if user_d.get("is_new_school", False) else []]))
    if(parallels == None): return
    user_d["classes"] = parallels
    await msg.edit_text(f"Успешно устновлено соединение с сайтом!\nВыберите класс, у которого вы являетесь классным руководителем:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(i.name, callback_data=f"main_class_t:{i.name}")] for i in parallels if(i.name.endswith('параллель'))]))
    cursor.execute("INSERT OR IGNORE INTO schools (number, name, website) VALUES (?, ?, ?)", (user_d['school_num'], user_d['school_name'], user_d['school_web']))
    pass

async def ChooseMainClassTeacher(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    user_d = users_data.get(sender.id, {})
    parallels:list[Parallel] = user_d.get('classes') 
    await msg.edit_reply_markup(reply_markup=None)
    if(parallels == None):
        await msg.edit_text(f"Произошла потеря данных, возможно бот был перезапущен, сожалеем, но придется перезаполнить данные использовав /menu")
        return
    chosen = args[0]
    main_parallel:Parallel = [i for i in parallels if(i.name == chosen)][0]
    possible_classes = {}
    for i in main_parallel.items:
        for j in i.items:
            x = j.name.replace(' ', '')
            possible_classes[x] = possible_classes.get(x, 0)+1
    possible_classes:dict[str, int] = dict(sorted(possible_classes.items(), key=lambda item: item[1], reverse=True))
    buttons = []
    for k in possible_classes.keys():
        if(k.find('-') == -1):
            buttons.append([InlineKeyboardButton(text=f"{k}", callback_data=f"main_class_choose_t:{k}")])
    user_d['class'] = main_parallel
    await msg.edit_text("Выберите класс для классного руководства, ОБРАТИТЕ ВНИМАНИЕ: не выбирайте подгруппы, выбирайте класс целиком (не 8а-1, а 8а)\n",reply_markup=InlineKeyboardMarkup(buttons))

async def MainClassTeacher(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    user_d = users_data.get(sender.id, {})
    parallel:Parallel = user_d.get('class')
    if(parallel == None):
        await msg.edit_text(f"Произошла потеря данных, возможно бот был перезапущен, сожалеем, но придется перезаполнить данные использовав /menu")
        return
    cursor.execute("SELECT id FROM dnevniks WHERE teacher_tid = ? AND school = ? AND class_name = ?", (sender.id,user_d['school_num'],args[0]))
    sql_answer = cursor.fetchone()
    if(sql_answer != None):
        await msg.reply_html(f"Этот класс уже имеет электронный дневник! Вы можете отредактировать его:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Редактировать", callback_data=f"edit_journal_t:{sql_answer[0]}")]]))
        return
    await msg.edit_reply_markup(reply_markup=None)

    school = user_d["school_num"]
    website = user_d['school_web']
    login = user_d['login']
    password = user_d['password']
    id_to_retrevie = None
    subjects = []
    for i in parallel.items:
        subjects.append(i.name)
        for j in i.items:
            j:Clazz = j
            x = j.name.replace(' ', '')
            if(x != args[0]): continue
            id_to_retrevie = j.c_id
            
    d = GetOrCreateDnevnikfromUD(user_d)
    await msg.edit_text(f"Извлекаем список учеников...\nЭто может занять некоторое время...")
    members = {}
    data = d.GetData(id_to_retrevie)
    for j in data['members']:
        members[j['id']] = j['alias']
    members:dict[int, str] = dict(sorted(members.items(), key=lambda item: item[1]))
    subjects = list(set(subjects))
    await msg.delete()
    t = ""
    for k,v in members.items():
        invite_code = GetStudentCode(k)
        cursor.execute("INSERT INTO students (school, class_name, student_id, alias, invite_code) VALUES (?, ?, ?, ?, ?)", (school, args[0], k, v, invite_code))
        t+= f"<code>{v}</code> <a href=\"{GetInviteLink(invite_code)}\">ссылка</a>\n"
    cursor.execute("INSERT OR IGNORE INTO dnevniks (school, website, class_name, login, password, teacher_tid) VALUES (?, ?, ?, ?, ?, ?)", (school, website, args[0], login, password, sender.id))
    await msg.reply_text(f"Успешно подключен дневник для {args[0]} класса\n\nПредметы: {', '.join(subjects)}\n\nУченики:\n{t}", parse_mode='HTML', disable_web_page_preview=True)
async def StartTeacherProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.edit_reply_markup(reply_markup=None)
    await msg.edit_text(f"Если Вы являетесь <b>УЧИТЕЛЕМ</b>, то, чтобы сделать электронный дневник для вашего класс без госуслуг, вам необходимо ввести <u><b>номер вашей школы</b></u>(Только номер: без ГБОУ, ФМЛ и тд.):", parse_mode="HTML")
    users_state[sender.id] = UStates.AWAIT_OO_NUMBER_TEACHER

async def EnterLoginTeacher(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.edit_reply_markup(reply_markup=None)
    await msg.reply_html("Введите <u><b>ваш логин в системе Параграф</b></u>:")
    users_state[sender.id] = UStates.AWAIT_LOGIN_T

async def EnterWebTeacher(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.edit_reply_markup(reply_markup=None)
    await msg.reply_html("Введите <u><b>внешний веб адрес системы Параграф</b></u> (тот в котором вы можете ставить оценки из дома), просьба вводить без https:// или http:// :")
    users_state[sender.id] = UStates.AWAIT_OO_WEBSITE_T

async def EditJournalsProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    #await msg.edit_reply_markup(reply_markup=None)
    offset = int(args[0])
    cursor.execute("SELECT id, school, class_name FROM dnevniks WHERE teacher_tid = ? LIMIT 5 OFFSET ?", (sender.id, offset))
    journals = cursor.fetchall()
    buttons = []
    if(offset > 0):
        buttons.append([InlineKeyboardButton("Предыдущая страница", callback_data=f"edit_journals_t:{offset-5}")])
    for i in journals:
        buttons.append([InlineKeyboardButton(f"{i[1]} {i[2]}",callback_data=f"edit_journal_t:{i[0]}")])
    if(len(journals) >= 5):
        buttons.append([InlineKeyboardButton("Следующая страница", callback_data=f"edit_journals_t:{offset+5}")])
    buttons.append(CLOSE_BUTTON)
    await msg.reply_html("Выберите журнал для редактирования:", reply_markup=InlineKeyboardMarkup(buttons))
    users_state[sender.id] = UStates.UNKNOWN

async def EditJournalProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    #await msg.edit_reply_markup(reply_markup=None)
    jid = int(args[0])
    cursor.execute("SELECT id, school, class_name, website, login, password, is_active FROM dnevniks WHERE teacher_tid = ? AND id = ?", (sender.id, jid))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
    await msg.edit_text(f"Журнал:<blockquote>Школа: {journal[1]}\nКласс: {journal[2]}\nВебсайт: {journal[3]}\nЛогин: {journal[4]}\nПароль: {journal[5]}{f"\n<b>Ваш журнал деактивирован из-за ошибки авторизации, попробуйте заного ввести логин и пароль или вебсайт! <u>(ВАШИ УЧЕНИКИ НЕ МОГУТ СМОТРЕТЬ ОЦЕНКИ И ДЗ)</u></b>" if not journal[6] else ""}</blockquote>", parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Управление доступом", callback_data=f"manage_j_access:{jid}")],[InlineKeyboardButton("Изменить вебсайт", callback_data=f"edit_dnevnik_web:{journal[0]}")],[InlineKeyboardButton("Изменить логин и пароль", callback_data=f"edit_dnevnik_lp:{journal[0]}")], [InlineKeyboardButton("Удалить журнал", callback_data=f"predelete_cd:{journal[0]}")], CLOSE_BUTTON]))
    users_state[sender.id] = UStates.UNKNOWN

async def EditJournalAccessProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    cursor.execute("SELECT school, class_name FROM dnevniks WHERE id = ? AND teacher_tid = ?", (jid, sender.id))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
    text = f"Нажмите на имя ученика, чтобы редактировать доступ\n<u>Школа {journal[0]} класс {journal[1]}</u>:\n"
    cursor.execute("SELECT id, alias, invite_code FROM students WHERE school = ? AND class_name = ? AND status = \"invite\"", (journal[0], journal[1]))
    invited = cursor.fetchall()
    cursor.execute("SELECT id, alias, invite_code FROM students WHERE school = ? AND class_name = ? AND status = \"student\"", (journal[0], journal[1]))
    active = cursor.fetchall()
    if(len(invited) > 0):
        text+="Приглашенные ученики:\n"
    for i in invited:
        text+=f"   <a href=\"t.me/pss_ednevnik_bot?start=qpea{i[2]}\">{i[1]}</a> - <a href=\"{GetInviteLink(i[2])}\">ссылка</a>\n"
    if(len(active) > 0):
        text+="Вошедшие ученики:\n"
    for i in active:
        text+=f"   <a href=\"t.me/pss_ednevnik_bot?start=qpea{i[2]}\">{i[1]}</a>\n"
    await msg.edit_text(text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Показать ссылки", callback_data=f"showLNK:{jid}")], [InlineKeyboardButton("Сбросить ссылки", callback_data=f"resetLNK:{jid}")], [InlineKeyboardButton("Завершить сессии", callback_data=f"closeSESSIONS:{jid}")], [InlineKeyboardButton("Назад", callback_data=f"edit_journal_t:{jid}")], CLOSE_BUTTON]))


async def ResetClassLinksProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    cursor.execute("SELECT school, class_name FROM dnevniks WHERE id = ? AND teacher_tid = ?", (jid, sender.id))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
    cursor.execute("SELECT id, student_id, alias FROM students WHERE school = ? AND class_name = ?", (journal[0], journal[1]))
    people = []
    for i in cursor.fetchall():
        c = GetStudentCode(i[1])
        cursor.execute("UPDATE students SET invite_code = ? WHERE id = ?", (c, i[0]))
        people.append((i[2], c))
    await msg.edit_text(f"Ссылки для входа учеников были обновлены, вот они:\n{'\n'.join([f"<b>{i[0]}</b> - <a href=\"{GetInviteLink(i[1])}\">ссылка</a>" for i in people])}", parse_mode='HTML', disable_web_page_preview=True,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"manage_j_access:{jid}")], CANCEL_BUTTON]))

async def RegenLinkProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    sid = int(args[1])
    cursor.execute("SELECT school, class_name FROM dnevniks WHERE id = ? AND teacher_tid = ?", (jid, sender.id))
    journal = cursor.fetchone()
    if(journal is None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
    cursor.execute("SELECT student_id, tid FROM students WHERE school = ? AND class_name = ? AND id = ?",
                   (journal[0], journal[1], sid))
    student = cursor.fetchone()
    if (student is None):
        await msg.edit_text("Мы не нашли такого ученика у вас... Если считаете это ошибкой, сообщите разработчику", reply_markup=DEV_CLOSE_RPMK)
        return
    new_code = GetStudentCode(student[0])
    if (student[1] != 0):
        try: await c.bot.send_message(chat_id=student[1], text="Ваш учитель завершил вашу сессию, попросите у него новую ссылку для авторизации!\nЕсли считаете это ошибкой, сообщиете разработчику", reply_markup=DEV_CLOSE_RPMK)
        except: pass
    cursor.execute("UPDATE students SET invite_code = ?, tid = 0 WHERE id = ?",
                   (new_code, sid))
    await msg.edit_text(f"Ученик был выброшен и его ссылка была изменена!\nСсылка: {GetInviteLink(new_code)}", reply_markup=CLOSE_RPMK)

async def ShowClassLinksProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    cursor.execute("SELECT school, class_name FROM dnevniks WHERE id = ? AND teacher_tid = ?", (jid, sender.id))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
    cursor.execute("SELECT alias, invite_code FROM students WHERE school = ? AND class_name = ?", (journal[0], journal[1]))
    await msg.edit_text(f"<b><u>Ссылки для входа учеников</u></b>:\n{'\n'.join([f"<b>{i[0]}</b> - <a href=\"{GetInviteLink(i[1])}\">ссылка</a>" for i in cursor.fetchall()])}", parse_mode='HTML', disable_web_page_preview=True,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"manage_j_access:{jid}")], CANCEL_BUTTON]))

async def PreDeleteStudentProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    sid = int(args[1])
    cursor.execute("SELECT alias FROM students WHERE id = ?", (sid,))
    alias = cursor.fetchone()
    if (alias is None):
        await msg.edit_text(text='Ученик не найден!', reply_markup=CLOSE_RPMK)
    await msg.reply_html(text=f'Вы действительно хотите удалить ученика <b>{alias[0]}</b>?\n<i>Это означает, что бот будет считать, что ученик не в вашем классе!</i>', 
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(text='Да, удалить', callback_data=f'delete_student:{args[0]}:{args[1]}')],
                            [InlineKeyboardButton(text='Нет, отмена', callback_data=f'delete_me')]]))
    
async def DeleteStudentProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    sid = int(args[1])
    cursor.execute("SELECT school, class_name FROM dnevniks WHERE id = ? AND teacher_tid = ?", (jid, sender.id))
    journal = cursor.fetchone()
    if(journal is None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
    cursor.execute("SELECT student_id, tid FROM students WHERE school = ? AND class_name = ? AND id = ?",
                   (journal[0], journal[1], sid))
    student = cursor.fetchone()
    if (student is None):
        await msg.edit_text("Мы не нашли такого ученика у вас... Если считаете это ошибкой, сообщите разработчику", reply_markup=DEV_CLOSE_RPMK)
        return
    cursor.execute("DELETE FROM students WHERE id = ?", (sid,))
    await msg.edit_text("Ученик был удален... Удачи ему/ей!", reply_markup=CLOSE_RPMK)

async def CloseSessionsProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    cursor.execute("SELECT school, class_name FROM dnevniks WHERE id = ? AND teacher_tid = ?", (jid, sender.id))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
    cursor.execute("SELECT id, student_id, alias, tid FROM students WHERE school = ? AND class_name = ? AND tid != 0", (journal[0], journal[1]))
    people = []
    for i in cursor.fetchall():
        c = GetStudentCode(i[1])
        cursor.execute("UPDATE students SET invite_code = ? AND tid = 0 WHERE id = ?", (c, i[0]))
        cursor.execute("INSERT INTO events (type, school, class, student_id, extra) VALUES (\"log_out\", ?, ?, ?, \"Ваш учитель выкинул вас из профиля\")", (journal[0], journal[1], i[2]))
        people.append((i[2], c))
    await msg.edit_text(f"Вошедшие ученики были выброшены из профилей, а так же были изменены их ссылки входа:\n{'\n'.join([f"<b>{i[0]}</b> - <a href=\"{GetInviteLink(i[1])}\">ссылка</a>" for i in people])}", parse_mode='HTML', disable_web_page_preview=True,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"manage_j_access:{jid}")], CANCEL_BUTTON]))


async def EditJournalWebProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    cursor.execute("SELECT id, school, class_name, website, login, password FROM dnevniks WHERE teacher_tid = ? AND id = ?", (sender.id, jid))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
        
    await msg.reply_html(f"Вы собираетесь изменить сайт Параграфа для журнала\n Школа: {journal[1]}\n Класс: {journal[2]}\n Старый вебсайт: {journal[3]}\n\nВведите <u><b>новый веб адрес журнала</b></u>:", reply_markup=CANCEL_RPMK)
    users_state[sender.id] = UStates.AWAIT_EDIT_WEB_T
    users_data[sender.id] = {"journal_id":jid}

async def EditJournalLPProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    cursor.execute("SELECT id, school, class_name, website, login, password FROM dnevniks WHERE teacher_tid = ? AND id = ?", (sender.id, jid))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
        
    await msg.reply_html(f"Вы собираетесь изменить сайт Параграфа для журнала\n<blockquote>Школа: {journal[1]}\nКласс: {journal[2]}\nСтарый логин: {journal[4]}\nСтарый пароль: {journal[5]}</blockquote>\n\nВведите <u><b>новый логин пароль</b></u> в сообщении в первой строке - логин, во второй - пароль:", reply_markup=CANCEL_RPMK)
    users_state[sender.id] = UStates.AWAIT_EDIT_LP_T
    users_data[sender.id] = {"journal_id":jid}


async def PreDeleteJournal(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    cursor.execute("SELECT id, school, class_name, website, login, password FROM dnevniks WHERE teacher_tid = ? AND id = ?", (sender.id, jid))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
        
    await msg.edit_text(f"Журнал:<blockquote>Школа: {journal[1]}\nКласс: {journal[2]}\nВебсайт: {journal[3]}\nЛогин: {journal[4]}\nПароль: {journal[5]}</blockquote>\nВы уверены, что хотите <b>удалить журнал</b>, это действие <u>необратимо</u>, а ваши ученики <u>потеряют доступ к оценкам</u>\nВЫ ХОТИТЕ УДАЛИТЬ ЖУРНАЛ?", parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Да, удалить", callback_data=f"delete_cd:{jid}")], [InlineKeyboardButton("Назад", callback_data=f"edit_journal_t:{jid}")], CLOSE_BUTTON]))

async def DeleteJournal(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    jid = int(args[0])
    cursor.execute("SELECT id, school, class_name, website, login, password FROM dnevniks WHERE teacher_tid = ? AND id = ?", (sender.id, jid))
    journal = cursor.fetchone()
    if(journal == None):
        await msg.edit_text("Такой журнал не найден у вас, попробуйте еще раз и убедитесь, что журнал все еще принадлежит вам", reply_markup=CLOSE_RPMK)
        return
    cursor.execute("DELETE FROM dnevniks WHERE id = ?", (jid,))
    await msg.edit_text(f"Журнал:<blockquote>Школа: {journal[1]}\nКласс: {journal[2]}\nВебсайт: {journal[3]}</blockquote>\nУдален!", parse_mode='HTML', reply_markup=CLOSE_RPMK)


async def EnterWebTeacher(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.edit_reply_markup(reply_markup=None)
    await msg.reply_html("Введите внешний веб адрес системы Параграф (тот в котором вы можете ставить оценки из дома), просьба вводить без https:// или http:// :")
    users_state[sender.id] = UStates.AWAIT_OO_WEBSITE_T
async def OOConfirmedProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.edit_reply_markup(reply_markup=None)
    if(users_state[sender.id] != UStates.AWAIT_OO_CONFIRM_T or users_data.get(sender.id, {}).get("school_num", None) == None):
        return
    
    await msg.reply_html(f"Введите ваш логин от системы Параграф (который вы используете при входе в электронный дневник):")
    users_state[sender.id] = UStates.AWAIT_LOGIN_T


async def MeStudentProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    code = args[0]
    cursor.execute("SELECT school, class_name, student_id, alias, status, tid FROM students WHERE invite_code = ?", (code,))
    invite = cursor.fetchone()
    if(invite == None):
        await msg.edit_text(f"Приглашение не найдено!")
        return
    if(invite[4] == "student"):
        await msg.edit_text(f"Приглашение уже использовали!\nЕсли это были не вы, то сообщите вашему учителю!\nИли обратитесь к разработчику и передайте следующую информацию: <code>{code}:{invite[5]}:{invite[3]}</code>", parse_mode='HTML', reply_markup=DEV_RPMK)
        return
    cursor.execute("UPDATE students SET tid = ?, status = \"student\" WHERE invite_code = ?", (sender.id, code))
    await msg.edit_text(f"{invite[3]}, поздравляем с успешным подключением электронного дневника прямо в телеграме!\nВы можете посмотреть информацию о вас и о уроках, использовав /profile")


async def UpdateFioSProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    cursor.execute("SELECT id, student_id, school, class_name, alias FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    if(student == None):
        await msg.reply_html("Вы не вошли в профиль!")
        return
    cursor.execute("SELECT website, login, password FROM dnevniks WHERE school = ? AND class_name = ?", (student[2], student[3]))
    d_entry = cursor.fetchone()
    if(d_entry == None):
        await msg.reply_html("Не найден электронный дневник для вашего класса, обратитесь к разработчику", reply_markup=DEV_RPMK)
        return
    d = GetOrCreateDnevnik(d_entry[0],d_entry[1],d_entry[2])
    clazz = RegExp.match("\\d{1,2}", student[3])
    if not (clazz):
        raise RuntimeError("Редкое явление - ошибка обновления имени: не удалось извлечь класс пользователя")
    clazz = clazz.group()
    parallels = d.GetParallels()
    parallel:Parallel = None
    for i in parallels:
        if(not i.name.startswith(clazz)): continue
        parallel = i
        break
    for j in parallel.items:
        for i in j.items:
            x = i.name.replace(' ', '')
            if(x != student[3]): continue
            data = d.GetData(i.c_id)
            for i in data['members']:
                if(f'{student[1]}' == i['id']):
                    cursor.execute("UPDATE students SET alias = ? WHERE id = ?", (i['alias'], student[0]))
                    await msg.reply_html(f"Ваше имя обновлено!\n<blockquote>Старое имя: {student[4]}\nНовое имя: {i['alias']}</blockquote>",reply_markup=CLOSE_RPMK)
                    return

async def ShowChooseTermProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    cursor.execute("SELECT school, class_name FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    if(student is None):
        await msg.edit_text("Вы не вошли как ученик, чтобы войти вам необходимо перейти по ссылке, которую отправил вам учитель!\n<i>Если возникают сложности, обращайтесь к разработчику!</i>", parse_mode='HTML', reply_markup=DEV_RPMK)
        return
    cursor.execute("SELECT date_from, date_to, number FROM periods WHERE school = ? AND class_name = ?", (student[0], student[1]))
    buttons = []
    text = "Доступные периоды:\n"
    for i in cursor.fetchall():
        text += f"{i[2]} период: {i[0]} -> {i[1]}\n"
        buttons.append([InlineKeyboardButton(text=f"{i[2]} период", callback_data=f"marks_by_term_s:{i[2]}")])
    buttons.append([InlineKeyboardButton(text="Итоговые", callback_data="show_final_marks_s")])
    buttons.append(CLOSE_BUTTON)
    await msg.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))

async def MarksByTermProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    term = int(args[0])
    cursor.execute("SELECT student_id, school, class_name FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    if(student is None):
        await msg.edit_text("Вы не вошли как ученик, чтобы войти вам необходимо перейти по ссылке, которую отправил вам учитель!\n<i>Если возникают сложности, обращайтесь к разработчику!</i>", parse_mode='HTML', reply_markup=DEV_RPMK)
        return
    cursor.execute("SELECT date_from, date_to FROM periods WHERE school = ? AND class_name = ? AND number = ?", (student[1], student[2], term))
    term = cursor.fetchone()
    if (term is None):
        await msg.edit_text("Период не найден!\nПопробуйте снова или обратитесь к разработчику", reply_markup=DEV_CLOSE_RPMK)
        return
    await chat.send_message(GetFullMarks(*student, date_from=term[0], date_to=term[1]), parse_mode='HTML', disable_web_page_preview=True, reply_markup=CLOSE_RPMK)
    

async def ShowFinalMarks(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    cursor.execute("SELECT student_id, school, class_name FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    if(student is None):
        await msg.edit_text("Вы не вошли как ученик, чтобы войти вам необходимо перейти по ссылке, которую отправил вам учитель!\n<i>Если возникают сложности, обращайтесь к разработчику!</i>", parse_mode='HTML', reply_markup=DEV_RPMK)
        return
    text = f"<i>Итоговые оценки:</i>\n"
    cursor.execute("SELECT DISTINCT subject_shr FROM lessons WHERE school = ? AND class_name IN (SELECT group_name FROM class_linking WHERE student_id = ? UNION SELECT ?)", (student[1], student[0], student[2]))
    for i in cursor.fetchall():
        cursor.execute("SELECT mark_char, text, value, cost FROM marks WHERE student_id = ? AND text = 'pSS:f1nAl' AND subject_shr = ? ORDER BY date ASC", (student[0], i[0]))
        sql_answer = cursor.fetchall()
        # link = GetStartLink(f"qmrks{i[0]}")
        text+=f"<b><a href='{GetStartLink(f"qmrks{i[0]}")}'>{GetShortcutText(i[0])}</a></b>: "
        text += ', '.join([f"{j}" for j,*q in sql_answer])
        text += "\n"
    await msg.reply_html(text=text, reply_markup=CLOSE_RPMK, disable_web_page_preview=True)


async def LogoutStudent(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    cursor.execute("SELECT status, tid, student_id, alias FROM students WHERE tid = ?", (sender.id,))
    student = cursor.fetchone()
    if(student == None):
        await msg.edit_text("Вы даже еще не вошли!")
        return
    cursor.execute("UPDATE students SET status = \"invite\", tid = 0, invite_code = ? WHERE tid = ?", (GetStudentCode(student[2]),sender.id))
    await msg.edit_text(f"{student[3]}, Вы вышли из аккаунта!")

async def NotMeStudentProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    await msg.edit_text(f"Сообщите учителю, что вам отправили не ту ссылку! Или сообщите разработчику", reply_markup=DEV_CLOSE_RPMK)



async def UnkonwnCLBProc(u: Update, c: ContextTypes.DEFAULT_TYPE, msg:Message, chat:Chat, sender:User, args:list[str]):
    raise RuntimeError(f"Unknown callback_data[{u.callback_query.data}]!")
#endregion


async def CallbackProc(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.callback_query.answer()
    data = u.callback_query.data
    cmd = data.split(':')[0]
    args = data.split(':')[1:]
    await CLB_COMMANDS.get(cmd, UnkonwnCLBProc)(u, c, u.effective_message, u.effective_chat, u.effective_sender, args)

async def ErrorProc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    error = context.error
    print(f"Error occured: {error} while proccessing message({msg})")
    if(msg != None):
        try:
            await msg.reply_html(f"<b>Произошла непредвиденная ошибка!</b>\n\nСообщите об этом инциденте разработчику: @possiug\n\n<tg-spoiler><i>Мы надеемся, что все будет хорошо</i></tg-spoiler>\n\nИнформация об ошибке:\n<tg-spoiler><i>{HTMLescape(error.__str__())}</i></tg-spoiler>", reply_markup=DEV_CLOSE_RPMK)
        except Exception as e:
            print(f"cannnot send error msg: {e}")



#region Listing
CLB_COMMANDS = {
    'test': TestProc,
    'te_log_pass': OOConfirmedProc,
    'enter_login_t': EnterLoginTeacher,
    'enter_web_t': EnterWebTeacher,
    'all_ok_tr':AllDataConfirmedProc,
    'main_class_t': ChooseMainClassTeacher,
    'main_class_choose_t': MainClassTeacher,
    'start_teacher': StartTeacherProc,
    'edit_journals_t': EditJournalsProc,
    'edit_journal_t': EditJournalProc,
    'edit_dnevnik_web': EditJournalWebProc,
    'edit_dnevnik_lp': EditJournalLPProc,
    'manage_j_access': EditJournalAccessProc,
    'showLNK': ShowClassLinksProc,
    'resetLNK': ResetClassLinksProc,
    'predelete_cd': PreDeleteJournal,
    'delete_cd': DeleteJournal,
    'its_me_s': MeStudentProc,
    'itsnt_me_s': NotMeStudentProc,
    'update_fio_s': UpdateFioSProc,
    'logout_s': LogoutStudent,
    'delete_me': DeleteMeProc,
    'cancel_me': CancelMeProc,
    'menu': Menu,
    'regenlink_t': RegenLinkProc,
    'predelete_student': PreDeleteStudentProc,
    'delete_student': DeleteStudentProc,
    'show_choose_term_s': ShowChooseTermProc,
    'marks_by_term_s': MarksByTermProc,
    'show_final_marks_s': ShowFinalMarks
}
#endregion

PrepareDB()

if (__name__ == '__main__'):
    application = ApplicationBuilder().token(BOT_TOKEN).build()   

    application.add_handler(CommandHandler("menu", MenuProc))
    application.add_handler(CommandHandler("profile", ProfileProc))
    application.add_handler(CommandHandler("status", StatusProc))
    application.add_handler(CommandHandler("admin", AdminProc))
    application.add_handler(CommandHandler("start", StartProc))
    application.add_handler(CommandHandler("dz", HomeWorkCMDProc))
    application.add_handler(CommandHandler("marks", MarksCMDProc))
    application.add_handler(MessageHandler(filters.ALL, MsgProc))
    application.add_handler(CallbackQueryHandler(CallbackProc))
    application.add_error_handler(ErrorProc)
    is_active = True
    thr = threading.Thread(target=asyncio.run, args=(mainLoop(),),daemon=True)
    thr.start()
    #asyncio.run(Loop())
    #exit()

    try:
        application.run_polling()
    except: pass
    finally:
        connection.commit()
        connection.close()
    is_active = False

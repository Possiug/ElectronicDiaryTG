import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, abort, render_template, make_response, send_file
from flask_cors import CORS, cross_origin

DB_FILENAME = "ed.db"

connection = sqlite3.connect(DB_FILENAME, check_same_thread=False)
cursor = connection.cursor()

app = Flask(__name__)
cors = CORS(app) # allow CORS for all domains on all routes.
app.config['CORS_HEADERS'] = 'Content-Type'

# ============= Работа с БД =============

def get_student_by_student_token(student_access: str):
    cursor.execute(
        """
        SELECT id, school, class_name, student_id, alias
        FROM students
        WHERE invite_code = ?
        """,
        (student_access,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "local_id": row[0],
        "school": row[1],
        "class_name": row[2],
        "student_id": row[3],
        "alias": row[4],
        "token": student_access
    }


def get_periods_for_class(school: int, class_name: str):
    cursor.execute(
        """
        SELECT date_from, date_to, number
        FROM periods
        WHERE school = ? AND class_name = ?
        ORDER BY number
        """,
        (school, class_name),
    )
    rows = cursor.fetchall()
    return [
        {"date_from": d_from, "date_to": d_to, "number": num}
        for (d_from, d_to, num) in rows
    ]


def get_subjects_for_student(student_par_id: int, school: int, class_name: str):
    """
    Предметы из lessons + подгруппы через class_linking.
    """
    cursor.execute(
        """
        SELECT DISTINCT subject_shr
        FROM lessons
        WHERE school = ?
          AND class_name IN (
              SELECT group_name
              FROM class_linking
              WHERE student_id = ?
              UNION
              SELECT ?
          )
        """,
        (school, student_par_id, class_name),
    )
    return [row[0] for row in cursor.fetchall()]


def get_subject_name(subject_shr: int) -> str:
    cursor.execute("SELECT text FROM shortcuts WHERE id = ?", (subject_shr,))
    row = cursor.fetchone()
    return row[0] if row else f"Предмет {subject_shr}"


def mean_weighted(values_with_weights):
    num = 0.0
    den = 0.0
    for v, w in values_with_weights:
        if not w:
            continue
        num += v * w
        den += w
    if den == 0:
        return None
    return round(num / den, 2)


def get_marks_for_subject_period(student_par_id, school, subject_shr, date_from, date_to):
    """
    Обычные оценки (НЕ четвертные) за период.
    """
    cursor.execute(
        """
        SELECT mark_char, value, cost, date
        FROM marks
        WHERE student_id = ?
          AND school = ?
          AND subject_shr = ?
          AND text != 'pSS:f1nAl'
          AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        (student_par_id, school, subject_shr, date_from, date_to),
    )
    rows = cursor.fetchall()

    marks = []
    weighted = []

    for ch, val, cost, dt in rows:
        marks.append({"char": ch, "value": val, "cost": cost, "date": dt})
        if val:
            weighted.append((val, cost))

    return marks, mean_weighted(weighted)


def get_final_mark_for_subject_period(student_par_id, school, subject_shr, date_from, date_to):
    """
    Четвертная оценка (text='pSS:f1nAl'), если есть.
    """
    cursor.execute(
        """
        SELECT value, mark_char, date
        FROM marks
        WHERE student_id = ?
          AND school = ?
          AND subject_shr = ?
          AND text = 'pSS:f1nAl'
          AND date BETWEEN ? AND ?
        ORDER BY date DESC
        LIMIT 1
        """,
        (student_par_id, school, subject_shr, date_from, date_to),
    )
    row = cursor.fetchone()
    if not row:
        return None, None
    value, ch, dt = row
    return value, ch


def build_homework_data(student: dict):
    """
    Подгружаем ДЗ по логике как в GetFullHomework / GetHTMLSubjectHomework:
    - таблица lessons.homework
    - учитываем подгруппы через class_linking
    - берём ДЗ в окне +-7 дней вокруг текущей даты
    - прикреплённые файлы из files
    Возвращаем структуру:
    [
      {
        "subject_shr": ...,
        "subject_name": "...",
        "items": [
          {
            "date": "2024-09-15",
            "text": "сделать №214, 215",
            "files": [ {"hash": "...", "name": "файл.pdf"}, ... ]
          },
          ...
        ]
      },
      ...
    ]
    """
    school     = student["school"]
    class_name = student["class_name"]
    stud_par   = student["student_id"]
    token   = student["token"]

    # какие предметы вообще есть у ученика
    cursor.execute(
        """
        SELECT DISTINCT subject_shr
        FROM lessons
        WHERE school = ?
          AND class_name IN (
              SELECT group_name FROM class_linking WHERE student_id = ?
              UNION
              SELECT ?
          )
        """,
        (school, stud_par, class_name),
    )
    subjects = [row[0] for row in cursor.fetchall()]

    # окно дат как в боте: от now-7д до now+7д (по умолчанию)
    cursor.execute(
        "SELECT date('now', ?), date('now', ?)",
        ('-7 days', '7 days')
    )
    start_date, stop_date = cursor.fetchone()

    result = []

    for subj_shr in subjects:
        cursor.execute(
            """
            SELECT homework, date, id
            FROM lessons
            WHERE school = ?
              AND subject_shr = ?
              AND date >= ?
              AND date <= ?
              AND class_name IN (
                  SELECT group_name
                  FROM class_linking
                  WHERE student_id = ? AND subject_shr = ?
                  UNION
                  SELECT ?
              )
            ORDER BY date DESC, num DESC
            LIMIT 5
            """,
            (school, subj_shr, start_date, stop_date,
             stud_par, subj_shr, class_name),
        )
        rows = cursor.fetchall()
        items = []

        for hw_text, hw_date, lesson_id in rows:
            # прикреплённые файлы
            cursor.execute(
                "SELECT hashsum, file_name FROM files WHERE school = ? AND lesson_id = ?",
                (school, lesson_id),
            )
            files_rows = cursor.fetchall()
            files = [{"hash": h, "name": n, "link": f"/api/file/{token}/{h}"} for (h, n) in files_rows]

            text = hw_text if hw_text is not None else ""
            # если нет текста и нет файлов – смысла выводить строку нет
            if (text.strip() == "" and not files):
                continue

            items.append(
                {
                    "date": hw_date,
                    "text": text,
                    "files": files,
                }
            )

        result.append(
            {
                "subject_shr": subj_shr,
                "subject_name": get_subject_name(subj_shr),
                "items": items,
            }
        )

    return result


def build_student_data(student_access: str):
    """
    Основная структура для фронта.
    """
    student = get_student_by_student_token(student_access)
    if not student:
        return None

    periods = get_periods_for_class(student["school"], student["class_name"])
    subjects_shr = get_subjects_for_student(
        student["student_id"], student["school"], student["class_name"]
    )

    result_periods = []

    for p in periods:
        date_from = p["date_from"]
        date_to = p["date_to"]
        subj_list = []
        all_vw = []

        for subj_id in subjects_shr:
            # четвертная оценка из БД (если есть)
            final_value, final_char = get_final_mark_for_subject_period(
                student_par_id=student["student_id"],
                school=student["school"],
                subject_shr=subj_id,
                date_from=date_from,
                date_to=date_to,
            )

            # обычные оценки за период
            marks, avg = get_marks_for_subject_period(
                student_par_id=student["student_id"],
                school=student["school"],
                subject_shr=subj_id,
                date_from=date_from,
                date_to=date_to,
            )

            for m in marks:
                if m["value"]:
                    all_vw.append((m["value"], m["cost"]))

            subj_list.append(
                {
                    "subject_shr": subj_id,
                    "subject_name": get_subject_name(subj_id),
                    "avg": avg,
                    "final_mark": final_value,
                    "final_mark_char": final_char,
                    "marks": marks,
                }
            )

        avg_total = mean_weighted(all_vw)

        result_periods.append(
            {
                "number": p["number"],
                "date_from": date_from,
                "date_to": date_to,
                "subjects": subj_list,
                "avg_total": avg_total,
            }
        )

    # домашка (независимо от четверти)
    homework = build_homework_data(student)

    return {"student": student, "periods": result_periods, "homework": homework}


# ============= Роут =============

@app.route("/student/<student_access>")
@cross_origin()
def student_page(student_access: int):
    data = build_student_data(student_access)
    if not data:
        abort(404, "Ученик не найден")

    data_json = json.dumps(data, ensure_ascii=False, default=str)
    return render_template("main.html", data_json=data_json, _external=True)

def get_quarter_by_date(school, class_name, date: str) -> int:
    cursor.execute("SELECT number FROM periods WHERE school = ? AND class_name = ? AND ? >= date_from ORDER BY number DESC", (school, class_name, date))
    res = cursor.fetchone()[0]
    print(f"{date} - {res}")
    return res

def get_subject_with_grades(school: int, class_name: str, id: int):
    cursor.execute(" \
        SELECT sh.text, m.value, m.cost, m.date, m.text \
        FROM marks m \
        JOIN shortcuts sh ON sh.id = m.subject_shr \
        WHERE m.school = ? AND m.student_id = ? \
        ORDER BY sh.text, m.date", (school, id))
    res = cursor.fetchall()
    cur_subject = None
    cur_dto = None
    res_list = []
    for i in res:
        value = int(i[1])
        if (value == 0):
            continue
        subject = i[0]
        cost = i[2]
        date = i[3]
        comment = i[4]
        is_final = comment == 'pSS:f1nAl'
        quarter = get_quarter_by_date(school, class_name, date)
        if (subject != cur_subject):
            cur_subject = subject
            cur_dto = {
                'name': cur_subject,
                'grades': []
            }
            print(cur_dto)
            res_list.append(cur_dto)
        
        cur_dto['grades'].append({
            'value': value,
            'coefficient': cost,
            'date': date,
            'comment': comment,
            'quarter': quarter
        })
    return res_list


def get_homework(school, class_name, student_id):
    cursor.execute("SELECT sh.text, l.homework, l.date, l.id " \
    "FROM lessons l " \
    "JOIN shortcuts sh ON sh.id = l.subject_shr " \
    "WHERE l.school = ? AND l.class_name in (SELECT group_name FROM class_linking WHERE student_id = ? UNION SELECT ?) AND l.homework IS NOT NULL AND trim(cast(l.homework as text)) != '' ORDER BY l.date DESC",
    (school, student_id, class_name,))
    res_list = []
    lessons = cursor.fetchall()
    cursor.execute("SELECT id, file_name, lesson_id FROM files WHERE school = ? AND lesson_id IN (SELECT id FROM lessons WHERE school = ? AND class_name in (SELECT group_name FROM class_linking WHERE student_id = ? UNION SELECT ?))", (school, school, student_id, class_name))
    files = cursor.fetchall()
    f_res: dict[int, list[dict]] = {}
    for i in files:
        tmp = f_res.get(i[2], [])
        tmp.append({
            "name": i[1],
            "id": i[0]
        })
        f_res[i[2]] = tmp
    for i in lessons:
        res_list.append({
            'subject': i[0],
            'task': i[1],
            'due_date': i[2],
            'files': f_res.get(i[3], [])
        })

    return res_list


@app.route("/api/diary/<student_access>")
def get_app_data(student_access: str):
    cursor.execute("SELECT school, class_name, student_id, alias FROM students WHERE invite_code = ?", (student_access,))
    student = cursor.fetchone()
    if (student is None):
        return make_response('student not found!', 404)
    subj_grades = get_subject_with_grades(student[0], student[1], student[2])
    homework = get_homework(student[0], student[1], student[2])
    profile = {
        'student_id': student[2],
        'class_name': student[1],
        'school': student[0],
        'name': student[3]
    }
    res = {
        'profile': profile,
        'homework': homework,
        'subjects': subj_grades
    }
    return res


@app.route("/api/file/<student_access>/<file_hash>")
def get_file(student_access: str, file_hash):
    cursor.execute("SELECT id FROM students WHERE invite_code = ?", (student_access,))
    student = cursor.fetchone()
    if (student is None):
        return make_response('Access denided', 404)
    cursor.execute("SELECT file, file_name FROM files WHERE hashsum = ?", (file_hash,))
    sql_ans = cursor.fetchone()
    if (sql_ans is None):
        return make_response("{\"err\":\"1\", \"error_msg\":\"File not found!\"}", 404)
    fn = sql_ans[0]
    name = sql_ans[1]
    if (not os.path.exists(fn)):
        return make_response("{\"err\":\"2\", \"error_msg\":\"File not downloaded!\"}", 404)
    return send_file(fn, download_name=name)

@app.route("/download/android")
def download_android():
    return send_file("resources/android.apk", download_name="diary.apk")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

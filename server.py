import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, abort, render_template
from flask_cors import CORS, cross_origin

DB_FILENAME = "ed.db"

connection = sqlite3.connect(DB_FILENAME, check_same_thread=False)
cursor = connection.cursor()

app = Flask(__name__)
cors = CORS(app) # allow CORS for all domains on all routes.
app.config['CORS_HEADERS'] = 'Content-Type'

# ============= Работа с БД =============

def get_student_by_student_id(student_id: int):
    """
    Ищем по students.student_id (ID в Параграфе),
    а не по локальному students.id.
    """
    cursor.execute(
        """
        SELECT id, school, class_name, student_id, alias
        FROM students
        WHERE student_id = ?
        """,
        (student_id,),
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
            files = [{"hash": h, "name": n} for (h, n) in files_rows]

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


def build_student_data(student_id_from_url: int):
    """
    Основная структура для фронта.
    """
    student = get_student_by_student_id(student_id_from_url)
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

@app.route("/student/<int:student_id>")
@cross_origin()
def student_page(student_id: int):
    data = build_student_data(student_id)
    if not data:
        abort(404, "Ученик не найден")

    data_json = json.dumps(data, ensure_ascii=False, default=str)
    return render_template("main.html", data_json=data_json, _external=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

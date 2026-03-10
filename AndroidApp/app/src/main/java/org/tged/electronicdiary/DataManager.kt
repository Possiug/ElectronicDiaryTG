package org.tged.electronicdiary

import android.content.Context
import org.json.JSONObject
import org.tged.electronicdiary.data.Grade
import org.tged.electronicdiary.data.HomeworkItem
import org.tged.electronicdiary.data.StudentProfile
import org.tged.electronicdiary.data.Subject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

class DataManager(private val context: Context) {

    var subjects: List<Subject> = emptyList()
        private set
    var homework: List<HomeworkItem> = emptyList()
        private set
    var profile: StudentProfile? = null
        private set
    var loadError: String? = null
        private set
    /** true, если сервер вернул 404 — ученик не найден. */
    var studentNotFound: Boolean = false
        private set

    /**
     * Загружает дневник с сервера по ID ученика, при ошибке — из assets/data.json.
     * Вызов callback — из фонового потока; для обновления UI вызовите runOnUiThread в callback.
     */
    fun loadData(studentId: String, callback: (Boolean) -> Unit) {
        loadError = null
        studentNotFound = false
        Thread {
            var success = loadFromServer(studentId)
            if (!success && !studentNotFound) {
                val fromAssets = readJsonFromAssets()
                if (fromAssets != null) {
                    try {
                        val root = JSONObject(fromAssets)
                        subjects = parseSubjects(root)
                        homework = parseHomework(root)
                        profile = parseProfile(root)
                        loadError = null
                        success = true
                    } catch (_: Exception) { }
                }
                if (!success && loadError == null) {
                    loadError = context.getString(R.string.error_network)
                }
            }
            callback(success)
        }.start()
    }

    /** Загрузка с DiaryServer API по переданному ID ученика. */
    private fun loadFromServer(studentId: String): Boolean {
        val url = URL("$DIARY_SERVER_BASE_URL/api/diary/$studentId")
        var conn: HttpURLConnection? = null
        return try {
            conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 10_000
            conn.readTimeout = 10_000
            when (conn.responseCode) {
                404 -> {
                    studentNotFound = true
                    loadError = context.getString(R.string.error_student_not_found)
                    return false
                }
                200 -> { }
                else -> return false
            }
            val json: String = BufferedReader(InputStreamReader(conn.inputStream)).use { it.readText() }
            conn.disconnect()
            conn = null
            val root = JSONObject(json)
            subjects = parseSubjects(root)
            homework = parseHomework(root)
            profile = parseProfile(root)
            true
        } catch (e: Exception) {
            loadError = context.getString(R.string.error_network)
            false
        } finally {
            conn?.disconnect()
        }
    }

    /** Синхронная загрузка только из assets (для SubjectGradesActivity и обратной совместимости). */
    fun loadDataSync() {
        loadError = null
        val json = readJsonFromAssets() ?: run {
            loadError = context.getString(R.string.error_cannot_open_data)
            return
        }
        try {
            val root = JSONObject(json)
            subjects = parseSubjects(root)
            homework = parseHomework(root)
            profile = parseProfile(root)
        } catch (e: Exception) {
            loadError = context.getString(R.string.error_parse_json, e.message)
        }
    }

    private fun parseProfile(root: JSONObject): StudentProfile? {
        val p = root.optJSONObject("profile") ?: return null
        val studentId = p.optString("studentId", "")
        if (studentId.length == 0) return null
        return StudentProfile(
            studentId = studentId,
            className = p.optString("className", ""),
            schoolNumber = p.optInt("schoolNumber", 0),
            name = p.optString("name").takeIf { it.isNotEmpty() }
        )
    }

    private fun readJsonFromAssets(): String? {
        return try {
            context.assets.open("data.json").use { input ->
                BufferedReader(InputStreamReader(input)).use { it.readText() }
            }
        } catch (_: Exception) {
            null
        }
    }

    companion object {
        /** Адрес DiaryServer.*/
        private const val DIARY_SERVER_BASE_URL = "http://188.227.14.206:5000/"
    }

    private fun parseSubjects(root: JSONObject): List<Subject> {
        val arr = root.optJSONArray("subjects") ?: return emptyList()
        val list = mutableListOf<Subject>()
        for (i in 0 until arr.length()) {
            val obj = arr.getJSONObject(i)
            val name = obj.optString("name", "")
            val gradesArr = obj.optJSONArray("grades")
            val grades = mutableListOf<Grade>()
            var sum = 0.0
            var coefSum = 0.0
            if (gradesArr != null) {
                for (j in 0 until gradesArr.length()) {
                    val g = gradesArr.getJSONObject(j)
                    val value = g.optInt("value", 0)
                    if (value == 0) continue // не показываем нулевые оценки
                    val coef = g.optDouble("coefficient", 1.0)
                    grades.add(
                        Grade(
                            value = value,
                            coefficient = coef,
                            date = g.optString("date", ""),
                            comment = g.optString("comment", ""),
                            quarter = g.optInt("quarter", 0)
                        )
                    )
                    sum += value * coef
                    coefSum += coef
                }
            }
            val avg = if (coefSum > 0) sum / coefSum else 0.0
            list.add(Subject(name = name, averageGrade = avg, gradesCount = grades.size, grades = grades))
        }
        return list
    }

    private fun parseHomework(root: JSONObject): List<HomeworkItem> {
        val arr = root.optJSONArray("homework") ?: return emptyList()
        val list = mutableListOf<HomeworkItem>()
        for (i in 0 until arr.length()) {
            val obj = arr.getJSONObject(i)
            list.add(
                HomeworkItem(
                    subject = obj.optString("subject", ""),
                    task = obj.optString("task", ""),
                    dueDate = obj.optString("dueDate", ""),
                    done = obj.optBoolean("done", false)
                )
            )
        }
        return list
    }

    fun getGradesForSubject(subjectName: String): List<Grade> {
        return subjects.find { it.name == subjectName }?.grades ?: emptyList()
    }

    fun getSubjectAverage(subjectName: String): Double {
        return subjects.find { it.name == subjectName }?.averageGrade ?: 0.0
    }
}

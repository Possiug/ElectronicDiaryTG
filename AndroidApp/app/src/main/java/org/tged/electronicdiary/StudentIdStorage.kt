package org.tged.electronicdiary

import android.content.Context
import org.json.JSONObject
import java.io.File

/**
 * Сохранение и чтение ID ученика в JSON-файле в внутреннем хранилище приложения.
 * Формат: { "idEntered": true, "studentId": 1234000255650 }
 */
object StudentIdStorage {
    private const val FILE_NAME = "student.json"
    private const val KEY_ID_ENTERED = "idEntered"
    private const val KEY_STUDENT_ID = "studentId"

    fun save(context: Context, studentId: String) {
        val file = File(context.filesDir, FILE_NAME)
        val json = JSONObject().apply {
            put(KEY_ID_ENTERED, true)
            put(KEY_STUDENT_ID, studentId)
        }
        file.writeText(json.toString())
    }

    /** Сбрасывает сохранённый ID (выход из аккаунта). */
    fun clear(context: Context) {
        File(context.filesDir, FILE_NAME).delete()
    }

    /**
     * @return сохранённый ID ученика или null, если ещё не вводили
     */
    fun load(context: Context): String? {
        val file = File(context.filesDir, FILE_NAME)
        if (!file.exists()) return null
        return try {
            val json = JSONObject(file.readText())
            if (!json.optBoolean(KEY_ID_ENTERED, false)) return null
            val id = json.optString(KEY_STUDENT_ID, "")
            if (id == "") null else id
        } catch (_: Exception) {
            null
        }
    }
}

package org.tged.electronicdiary

import android.app.Application

class ElectronicDiaryApp : Application() {
    /** Общий DataManager после успешной загрузки в MainActivity; используется в SubjectGradesActivity. */
    var dataManager: DataManager? = null
}

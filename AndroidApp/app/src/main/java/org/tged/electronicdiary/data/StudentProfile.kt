package org.tged.electronicdiary.data

data class StudentProfile(
    val studentId: String,
    val className: String,
    val schoolNumber: Int,
    val name: String? = null
)

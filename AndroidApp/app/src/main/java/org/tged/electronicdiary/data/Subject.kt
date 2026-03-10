package org.tged.electronicdiary.data

data class Subject(
    val name: String,
    val averageGrade: Double,
    val gradesCount: Int,
    val grades: List<Grade>
)

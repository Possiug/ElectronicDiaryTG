package org.tged.electronicdiary.data

data class Grade(
    val value: Int,
    val coefficient: Double = 1.0,
    val date: String = "",
    val comment: String = "",
    val quarter: Int = 0
)

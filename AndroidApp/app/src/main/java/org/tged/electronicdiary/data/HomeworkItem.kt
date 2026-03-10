package org.tged.electronicdiary.data

data class HomeworkItem(
    val subject: String,
    val task: String,
    val dueDate: String,
    val done: Boolean = false
)

package org.tged.electronicdiary

import android.os.Bundle
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.tged.electronicdiary.data.Grade
import org.tged.electronicdiary.databinding.ActivitySubjectGradesBinding
import org.tged.electronicdiary.databinding.ItemGradeBinding

class SubjectGradesActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val binding = ActivitySubjectGradesBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        binding.toolbar.setNavigationOnClickListener { finish() }

        val subjectName = intent.getStringExtra(EXTRA_SUBJECT_NAME) ?: ""
        val quarter = intent.getIntExtra(EXTRA_QUARTER, 1)
        supportActionBar?.title = subjectName

        val dataManager = (application as? ElectronicDiaryApp)?.dataManager
            ?: DataManager(this).also { it.loadDataSync() }
        val allGrades = dataManager.getGradesForSubject(subjectName)
        val grades = allGrades.filter { it.quarter == quarter && it.coefficient != 0.0 }
        val avg = if (grades.isEmpty()) 0.0 else {
            var sum = 0.0
            var coefSum = 0.0
            for (g in grades) {
                sum += g.value * g.coefficient
                coefSum += g.coefficient
            }
            if (coefSum > 0) sum / coefSum else 0.0
        }

        binding.avgGrade.text = if (avg > 0) "%.2f".format(avg) else "—"
        binding.recycler.layoutManager = LinearLayoutManager(this)
        binding.recycler.adapter = GradeAdapter(grades)
    }

    companion object {
        const val EXTRA_SUBJECT_NAME = "subject_name"
        const val EXTRA_QUARTER = "quarter"
    }
}

private class GradeAdapter(private val grades: List<Grade>) : RecyclerView.Adapter<GradeAdapter.VH>() {

    class VH(val b: ItemGradeBinding) : RecyclerView.ViewHolder(b.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        return VH(ItemGradeBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val g = grades[position]
        holder.b.value.text = g.value.toString()
        holder.b.comment.text = g.comment.ifEmpty { holder.itemView.context.getString(R.string.grade_default_comment) }
        holder.b.coefficient.text = "× ${g.coefficient}"
        holder.b.date.text = g.date
    }

    override fun getItemCount(): Int = grades.size
}

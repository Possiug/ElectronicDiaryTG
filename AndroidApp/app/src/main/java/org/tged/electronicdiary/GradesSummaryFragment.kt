package org.tged.electronicdiary

import android.os.Bundle
import android.graphics.Typeface
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.LinearLayout
import android.widget.TextView
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.tged.electronicdiary.data.Grade
import org.tged.electronicdiary.data.Subject
import org.tged.electronicdiary.databinding.FragmentGradesSummaryBinding
import org.tged.electronicdiary.databinding.ItemSubjectSummaryBinding

/** Элемент сводки: предмет, оценки за период (без четвертных), средний за период, четвертная оценка (если выставлена). */
data class SummaryItem(val subject: Subject, val quarterGrade: Int?)

class GradesSummaryFragment : androidx.fragment.app.Fragment() {

    private var _binding: FragmentGradesSummaryBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentGradesSummaryBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: android.view.View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val activity = requireActivity() as? MainActivity ?: return
        val dataManager = activity.getDataManager()

        val quarterLabels = listOf(
            getString(R.string.quarter_1),
            getString(R.string.quarter_2),
            getString(R.string.quarter_3),
            getString(R.string.quarter_4)
        )
        binding.quarterSpinner.adapter = ArrayAdapter(
            requireContext(),
            android.R.layout.simple_spinner_item,
            quarterLabels
        ).apply { setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }

        binding.quarterSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                activity.selectedQuarter = position + 1
                updateList(dataManager.subjects)
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }

        binding.recycler.layoutManager = LinearLayoutManager(requireContext())
        syncSpinnerAndUpdate(activity, dataManager.subjects)
    }

    override fun onResume() {
        super.onResume()
        val activity = requireActivity() as? MainActivity ?: return
        if (activity.selectedQuarter in 1..4) {
            binding.quarterSpinner.setSelection(activity.selectedQuarter - 1)
            updateList(activity.getDataManager().subjects)
        }
    }

    private fun syncSpinnerAndUpdate(activity: MainActivity, subjects: List<Subject>) {
        binding.quarterSpinner.setSelection(activity.selectedQuarter - 1)
        updateList(subjects)
    }

    private fun updateList(subjects: List<Subject>) {
        val quarter = (requireActivity() as? MainActivity)?.selectedQuarter ?: 1
        val items = buildSummaryItems(subjects, quarter)
        binding.recycler.adapter = SubjectSummaryAdapter(items) { }
    }

    /**
     * Оценки за период — только без четвертных (coefficient != 0).
     * Четвертная — только если выставлена (оценка pSS:f1nAl, coefficient == 0); иначе показываем "—".
     */
    private fun buildSummaryItems(subjects: List<Subject>, quarter: Int): List<SummaryItem> {
        val result = mutableListOf<SummaryItem>()
        for (s in subjects) {
            val gradesInQuarter = s.grades.filter { it.quarter == quarter }
            if (gradesInQuarter.isEmpty()) continue

            val periodGrades = gradesInQuarter.filter { it.coefficient != 0.0 }
            val quarterFinal = gradesInQuarter.firstOrNull { it.coefficient == 0.0 }?.value

            val avg = if (periodGrades.isNotEmpty()) {
                var sum = 0.0
                var coefSum = 0.0
                for (g in periodGrades) {
                    sum += g.value * g.coefficient
                    coefSum += g.coefficient
                }
                if (coefSum > 0) sum / coefSum else 0.0
            } else 0.0

            result.add(
                SummaryItem(
                    subject = Subject(
                        name = s.name,
                        averageGrade = avg,
                        gradesCount = periodGrades.size,
                        grades = periodGrades
                    ),
                    quarterGrade = quarterFinal
                )
            )
        }
        return result
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }
}

private class SubjectSummaryAdapter(
    private val items: List<SummaryItem>,
    private val onSubjectClick: (String) -> Unit
) : RecyclerView.Adapter<SubjectSummaryAdapter.VH>() {

    class VH(val b: ItemSubjectSummaryBinding) : RecyclerView.ViewHolder(b.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        return VH(ItemSubjectSummaryBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val (s, quarterGrade) = items[position]
        holder.b.subjectName.text = s.name
        val avgStr = if (s.averageGrade > 0) "%.1f".format(s.averageGrade) else "—"
        holder.b.avgGrade.text = avgStr
        holder.b.avgGrade.setTextColor(
            holder.itemView.context.getColor(
                when {
                    s.averageGrade >= 4.5 -> R.color.color_grade_high
                    s.averageGrade >= 3.5 -> R.color.color_grade_mid
                    else -> R.color.color_grade_low
                }
            )
        )
        holder.b.avgBg.setBackgroundResource(
            when {
                s.averageGrade >= 4.5 -> R.drawable.bg_grade_circle_high
                s.averageGrade >= 3.5 -> R.drawable.bg_grade_circle_mid
                else -> R.drawable.bg_grade_circle_low
            }
        )
        holder.b.quarterGrade.text = quarterGrade?.toString() ?: "—"
        holder.b.gradesContainer.removeAllViews()
        val ctx = holder.itemView.context
        val density = ctx.resources.displayMetrics.density
        val badgeSize = (36 * density).toInt()
        val margin = (6 * density).toInt()
        for (g in s.grades) {
            val tv = TextView(ctx).apply {
                text = g.value.toString()
                setTextColor(ctx.getColor(R.color.color_primary))
                textSize = 15f
                setTypeface(null, Typeface.BOLD)
                setPadding((12 * density).toInt(), (9 * density).toInt(), (12 * density).toInt(), (9 * density).toInt())
                layoutParams = LinearLayout.LayoutParams(badgeSize, badgeSize).apply {
                    marginEnd = margin
                    bottomMargin = margin
                }
                setBackgroundResource(R.drawable.bg_grade_badge)
            }
            holder.b.gradesContainer.addView(tv)
        }
    }

    override fun getItemCount(): Int = items.size
}

package org.tged.electronicdiary

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.tged.electronicdiary.data.Subject
import org.tged.electronicdiary.databinding.FragmentSubjectsBinding
import org.tged.electronicdiary.databinding.ItemSubjectRowBinding

class SubjectsFragment : androidx.fragment.app.Fragment() {

    private var _binding: FragmentSubjectsBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): android.view.View {
        _binding = FragmentSubjectsBinding.inflate(inflater, container, false)
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
        syncSpinnerAndUpdate(dataManager.subjects)
    }

    override fun onResume() {
        super.onResume()
        val activity = requireActivity() as? MainActivity ?: return
        if (activity.selectedQuarter in 1..4) {
            binding.quarterSpinner.setSelection(activity.selectedQuarter - 1)
            updateList(activity.getDataManager().subjects)
        }
    }

    private fun syncSpinnerAndUpdate(subjects: List<Subject>) {
        binding.quarterSpinner.setSelection((requireActivity() as? MainActivity)?.selectedQuarter?.minus(1) ?: 0)
        updateList(subjects)
    }

    private fun updateList(subjects: List<Subject>) {
        val activity = requireActivity() as? MainActivity ?: return
        val dataManager = activity.getDataManager()
        val quarter = activity.selectedQuarter
        val filtered = subjects.mapNotNull { s ->
            val gradesInQuarter = s.grades.filter { it.quarter == quarter }
            if (gradesInQuarter.isEmpty()) return@mapNotNull null
            var sum = 0.0
            var coefSum = 0.0
            for (g in gradesInQuarter) {
                sum += g.value * g.coefficient
                coefSum += g.coefficient
            }
            val avg = if (coefSum > 0) sum / coefSum else 0.0
            val subj = Subject(s.name, avg, gradesInQuarter.size, gradesInQuarter)
            val lastHw = dataManager.homework
                .filter { it.subject.equals(s.name, ignoreCase = true) }
                .maxByOrNull { it.dueDate }
                ?.task
            Pair(subj, lastHw)
        }
        binding.recycler.adapter = SubjectRowAdapter(filtered) { name ->
            activity.openSubjectGrades(name)
        }
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }
}

private class SubjectRowAdapter(
    private val items: List<Pair<Subject, String?>>,
    private val onSubjectClick: (String) -> Unit
) : RecyclerView.Adapter<SubjectRowAdapter.VH>() {

    class VH(val b: ItemSubjectRowBinding) : RecyclerView.ViewHolder(b.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        return VH(ItemSubjectRowBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val (s, lastHw) = items[position]
        holder.b.subjectName.text = s.name
        holder.b.avgGrade.text = if (s.averageGrade > 0) "%.1f".format(s.averageGrade) else "—"
        if (!lastHw.isNullOrBlank()) {
            holder.b.lastHomework.visibility = View.VISIBLE
            holder.b.lastHomework.text = lastHw
        } else {
            holder.b.lastHomework.visibility = View.GONE
        }
        holder.itemView.setOnClickListener { onSubjectClick(s.name) }
    }

    override fun getItemCount(): Int = items.size
}

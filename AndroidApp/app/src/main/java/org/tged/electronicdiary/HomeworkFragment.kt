package org.tged.electronicdiary

import android.os.Bundle
import android.graphics.drawable.GradientDrawable
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.tged.electronicdiary.data.HomeworkItem
import org.tged.electronicdiary.databinding.FragmentHomeworkBinding
import org.tged.electronicdiary.databinding.ItemHomeworkBinding

class HomeworkFragment : androidx.fragment.app.Fragment() {

    private var _binding: FragmentHomeworkBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): android.view.View {
        _binding = FragmentHomeworkBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: android.view.View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val activity = requireActivity() as? MainActivity ?: return
        binding.recycler.layoutManager = LinearLayoutManager(requireContext())
        binding.recycler.adapter = HomeworkAdapter(activity.getDataManager().homework)
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }
}

private class HomeworkAdapter(private val items: List<HomeworkItem>) :
    RecyclerView.Adapter<HomeworkAdapter.VH>() {

    class VH(val b: ItemHomeworkBinding) : RecyclerView.ViewHolder(b.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        return VH(ItemHomeworkBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val h = items[position]
        holder.b.subject.text = h.subject
        holder.b.task.text = h.task
        holder.b.dueDate.text = "📅 ${h.dueDate}"
        holder.b.statusIcon.text = if (h.done) "✓" else "•"
        val ctx = holder.itemView.context
        val color = if (h.done) ctx.getColor(R.color.color_success) else ctx.getColor(R.color.color_primary)
        val alphaColor = (if (h.done) 0x33 else 0x1F) shl 24 or (color and 0x00FFFFFF)
        holder.b.statusBg.background = GradientDrawable().apply {
            setShape(GradientDrawable.OVAL)
            setColor(alphaColor)
        }
        holder.b.statusIcon.setTextColor(color)
    }

    override fun getItemCount(): Int = items.size
}

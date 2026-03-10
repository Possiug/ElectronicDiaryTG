package org.tged.electronicdiary

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import org.tged.electronicdiary.data.StudentProfile
import org.tged.electronicdiary.databinding.FragmentProfileBinding

class ProfileFragment : androidx.fragment.app.Fragment() {

    private var _binding: FragmentProfileBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentProfileBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val activity = requireActivity() as? MainActivity ?: return
        val dataManager = activity.getDataManager()

        val profile = dataManager.profile ?: run {
            val savedId = StudentIdStorage.load(requireContext())
            if (savedId != null) {
                StudentProfile(studentId = savedId, className = "", schoolNumber = 0, name = null)
            } else null
        }

        binding.profileStudentId.text = profile?.studentId?.toString() ?: "—"
        binding.profileClassName.text = profile?.className?.ifEmpty { "—" } ?: "—"
        binding.profileSchoolNumber.text = if (profile != null && profile.schoolNumber > 0) {
            profile.schoolNumber.toString()
        } else "—"
        if (!profile?.name.isNullOrBlank()) {
            binding.profileNameRow.visibility = View.VISIBLE
            binding.profileName.text = profile!!.name
        } else {
            binding.profileNameRow.visibility = View.GONE
        }

        binding.profileLogoutButton.setOnClickListener {
            StudentIdStorage.clear(requireContext())
            startActivity(Intent(requireContext(), MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            })
            activity.finish()
        }
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }
}

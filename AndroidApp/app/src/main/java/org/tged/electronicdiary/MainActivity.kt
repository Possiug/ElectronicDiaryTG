package org.tged.electronicdiary

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter
import com.google.android.material.tabs.TabLayoutMediator
import org.tged.electronicdiary.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var dataManager: DataManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        dataManager = DataManager(this)
        val savedId = StudentIdStorage.load(this)

        if (savedId == null) {
            showIdInputScreen()
        } else {
            startLoadingData(savedId)
        }
    }

    private fun showIdInputScreen() {
        binding.idInputLayout.visibility = View.VISIBLE
        binding.loadingLayout.visibility = View.GONE
        binding.mainContent.visibility = View.GONE

        binding.studentIdSaveButton.setOnClickListener {
            val raw = binding.studentIdInput.text?.toString()?.trim() ?: ""
            val id = raw
            if (id == "") {
                Toast.makeText(this, getString(R.string.student_id_invalid), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            StudentIdStorage.save(this, id)
            binding.idInputLayout.visibility = View.GONE
            startLoadingData(id)
        }
    }

    private fun startLoadingData(studentId: String) {
        binding.loadingLayout.visibility = View.VISIBLE
        binding.mainContent.visibility = View.GONE

        dataManager.loadData(studentId) { success ->
            runOnUiThread {
                binding.loadingLayout.visibility = View.GONE
                if (success) {
                    (application as ElectronicDiaryApp).dataManager = dataManager
                    binding.mainContent.visibility = View.VISIBLE
                    val adapter = MainPagerAdapter(this)
                    binding.viewPager.adapter = adapter
                    TabLayoutMediator(binding.tabLayout, binding.viewPager) { tab, position ->
                        tab.text = when (position) {
                            0 -> getString(R.string.tab_summary)
                            1 -> getString(R.string.tab_homework)
                            2 -> getString(R.string.tab_subjects)
                            3 -> getString(R.string.tab_support)
                            4 -> getString(R.string.tab_profile)
                            else -> ""
                        }
                    }.attach()
                } else {
                    if (dataManager.studentNotFound) {
                        StudentIdStorage.clear(this)
                        binding.idInputLayout.visibility = View.VISIBLE
                        binding.mainContent.visibility = View.GONE
                    } else {
                        binding.mainContent.visibility = View.VISIBLE
                    }
                    AlertDialog.Builder(this)
                        .setMessage(dataManager.loadError ?: getString(R.string.error_network))
                        .setPositiveButton(getString(R.string.ok), null)
                        .show()
                }
            }
        }
    }

    fun getDataManager(): DataManager = dataManager

    var selectedQuarter: Int = 1
        set(value) { field = value.coerceIn(1, 4) }

    fun openSubjectGrades(subjectName: String) {
        startActivity(Intent(this, SubjectGradesActivity::class.java).apply {
            putExtra(SubjectGradesActivity.EXTRA_SUBJECT_NAME, subjectName)
            putExtra(SubjectGradesActivity.EXTRA_QUARTER, selectedQuarter)
        })
    }

    private inner class MainPagerAdapter(fa: FragmentActivity) : FragmentStateAdapter(fa) {
        override fun getItemCount(): Int = 5
        override fun createFragment(position: Int): Fragment = when (position) {
            0 -> GradesSummaryFragment()
            1 -> HomeworkFragment()
            2 -> SubjectsFragment()
            3 -> TechSupportFragment()
            4 -> ProfileFragment()
            else -> GradesSummaryFragment()
        }
    }
}

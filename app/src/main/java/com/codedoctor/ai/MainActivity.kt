package com.codedoctor.ai

import android.app.Activity
import android.content.Intent
import android.content.ClipboardManager
import android.content.ClipData
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.chaquo.python.Python
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    private lateinit var editor: EditText
    private lateinit var output: TextView
    private lateinit var copyButton: Button
    private lateinit var exportButton: Button

    private val filePicker = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.data?.let { uri ->
                try {
                    val text = contentResolver.openInputStream(uri)
                        ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }
                    if (text != null) {
                        editor.setText(text)
                        Toast.makeText(this, "تم تحميل الملف", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    Toast.makeText(this, "تعذرت قراءة الملف: " + e.message, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private val reportSaver = registerForActivityResult(
        ActivityResultContracts.CreateDocument("text/plain")
    ) { uri ->
        if (uri != null) {
            try {
                contentResolver.openOutputStream(uri)?.bufferedWriter(Charsets.UTF_8)?.use {
                    it.write(output.text.toString())
                }
                Toast.makeText(this, "تم حفظ التقرير", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                Toast.makeText(this, "تعذر حفظ التقرير: " + e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(22, 20, 22, 20)
            layoutDirection = View.LAYOUT_DIRECTION_RTL
            setBackgroundColor(0xFFF3F6FA.toInt())
        }
        page.addView(TextView(this).apply {
            text = "CODE DOCTOR AI"
            textSize = 25f
            gravity = Gravity.CENTER
            setTextColor(0xFF172A46.toInt())
        }, wrap())
        page.addView(TextView(this).apply {
            text = "طبيب الأكواد — تحليل Python محلياً"
            textSize = 15f
            gravity = Gravity.CENTER
            setPadding(0, 8, 0, 12)
        }, wrap())
        page.addView(Button(this).apply {
            text = "اختيار ملف Python"
            setOnClickListener {
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "text/*"
                }
                filePicker.launch(intent)
            }
        }, wrap())

        editor = EditText(this).apply {
            hint = "الصق كود Python هنا..."
            gravity = Gravity.TOP or Gravity.START
            minLines = 9
            maxLines = 16
            setSingleLine(false)
            textSize = 14f
            typeface = android.graphics.Typeface.MONOSPACE
            textDirection = View.TEXT_DIRECTION_LTR
            setText("def calculate(a, b):\n    return a / 0\n")
        }
        page.addView(editor, LinearLayout.LayoutParams(-1, 0, 1f).apply {
            topMargin = 8; bottomMargin = 8
        })

        val editorActions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        editorActions.addView(Button(this@MainActivity).apply {
            text = "مسح الكود"
            setOnClickListener { editor.setText("") }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        editorActions.addView(Button(this@MainActivity).apply {
            text = "نسخ الكود"
            setOnClickListener {
                val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
                clipboard.setPrimaryClip(ClipData.newPlainText("Python source", editor.text))
                Toast.makeText(this@MainActivity, "تم نسخ الكود", Toast.LENGTH_SHORT).show()
            }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        page.addView(editorActions, wrap())

        page.addView(Button(this).apply {
            text = "افحص الكود الآن"
            setOnClickListener { analyzeCode() }
        }, wrap())

        page.addView(Button(this).apply {
            text = "اقترح إصلاح الكود"
            setOnClickListener { suggestFix() }
        }, wrap())
        output = TextView(this).apply {
            text = "نتائج الفحص ستظهر هنا."
            textSize = 14f
            setTextColor(0xFF17243A.toInt())
            setPadding(10, 14, 10, 14)
            textDirection = View.TEXT_DIRECTION_RTL
        }
        page.addView(ScrollView(this).apply { addView(output) },
            LinearLayout.LayoutParams(-1, 0, 1f).apply { topMargin = 8 })

        val reportActions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        copyButton = Button(this@MainActivity).apply {
            text = "نسخ التقرير"
            isEnabled = false
            setOnClickListener {
                val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
                clipboard.setPrimaryClip(ClipData.newPlainText("Code Doctor AI report", output.text))
                Toast.makeText(this@MainActivity, "تم نسخ التقرير", Toast.LENGTH_SHORT).show()
            }
        }
        exportButton = Button(this@MainActivity).apply {
            text = "حفظ التقرير"
            isEnabled = false
            setOnClickListener { reportSaver.launch("code-doctor-report.txt") }
        }
        reportActions.addView(copyButton, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        reportActions.addView(exportButton, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        page.addView(reportActions, wrap())

        page.addView(Button(this).apply {
            text = "حول التطبيق"
            setOnClickListener {
                val version = try {
                    packageManager.getPackageInfo(packageName, 0).versionName ?: "غير معروف"
                } catch (_: Exception) {
                    "غير معروف"
                }
                android.app.AlertDialog.Builder(this@MainActivity)
                    .setTitle("حول CODE DOCTOR AI")
                    .setMessage("طبيب الأكواد — تحليل Python محلياً\\nالإصدار: $version\\n\\nالفحص يتم على الهاتف ولا يتم رفع الكود إلى الإنترنت.")
                    .setPositiveButton("حسناً", null)
                    .show()
            }
        }, wrap())

        page.addView(Button(this).apply {
            text = "سجل الفحوصات السابقة"
            setOnClickListener { showHistory() }
        }, wrap())

        page.addView(TextView(this).apply {
            text = "الفحص محلي — لا يتم رفع الكود إلى الإنترنت. النتائج تعتمد على القواعد الحالية ولا تثبت خلو البرنامج من الأخطاء."
            gravity = Gravity.CENTER
            textSize = 11f
        }, wrap())
        setContentView(ScrollView(this).apply { addView(page) })
    }

    private fun analyzeCode() {
        val source = editor.text.toString()
        copyButton.isEnabled = false
        exportButton.isEnabled = false
        if (source.isBlank()) {
            output.text = "أدخل كوداً أولاً."
            return
        }
        if (source.length > 50000) {
            output.text = "حجم الكود كبير جداً. اختصر الملف إلى 50 ألف حرف أو أقل لتجنب بطء الهاتف."
            return
        }
        try {
            val raw = Python.getInstance().getModule("analyzer")
                .callAttr("analyze", source).toString()
            val data = JSONObject(raw)
            val issues = data.getJSONArray("issues")
            val errors = countSeverity(issues, "ERROR")
            val warnings = countSeverity(issues, "WARNING")
            val infos = countSeverity(issues, "INFO")
            val status = when (data.optString("status")) {
                "SYNTAX_ERROR" -> "خطأ في صياغة Python"
                "ISSUES_FOUND" -> "تم العثور على ملاحظات"
                else -> "لم ترصد القواعد الحالية مشكلة"
            }
            val report = StringBuilder()
            report.append("CODE DOCTOR AI\n")
                .append("حالة الفحص: ").append(status).append("\n")
                .append("عدد الملاحظات: ").append(issues.length()).append("\n")
                .append("أخطاء: ").append(errors)
                .append(" | تحذيرات: ").append(warnings)
                .append(" | معلومات: ").append(infos).append("\n\n")
            if (issues.length() == 0) {
                report.append("لم تعثر القواعد الحالية على مشكلة. هذا لا يثبت خلو الكود من الأخطاء.\n")
            } else {
                for (i in 0 until issues.length()) {
                    val item = issues.getJSONObject(i)
                    val severity = when (item.optString("severity")) {
                        "CRITICAL" -> "حرج"
                        "ERROR" -> "خطأ"
                        "WARNING" -> "تحذير"
                        else -> "معلومة"
                    }
                    val confidence = if (item.optString("confidence") == "CONFIRMED") {
                        "خطأ مؤكد"
                    } else {
                        "احتمال يحتاج مراجعة"
                    }
                    report.append("• ").append(severity)
                        .append(" — ").append(item.optString("title"))
                        .append("\nالسطر: ").append(item.optInt("line"))
                        .append("\nدرجة الثقة: ").append(confidence)
                        .append("\n").append(item.optString("message"))
                        .append("\nاقتراح: ").append(item.optString("suggestion"))
                        .append("\n\n")
                }
            }
            val notice = data.optString("notice")
            if (notice.isNotBlank()) report.append("تنبيه: ").append(notice)
            output.text = report.toString()
            copyButton.isEnabled = true
            exportButton.isEnabled = true
            saveHistory(source, report.toString())
        } catch (e: Exception) {
            output.text = "وقع خطأ أثناء التحليل:\n" + e.message
            copyButton.isEnabled = true
        }
    }

    private fun suggestFix() {
        val source = editor.text.toString()
        if (source.isBlank()) {
            Toast.makeText(this, "أدخل كوداً أولاً.", Toast.LENGTH_SHORT).show()
            return
        }
        try {
            val raw = Python.getInstance().getModule("fixer").callAttr("fix_code", source).toString()
            val result = JSONObject(raw)
            if (!result.optBoolean("can_apply", false)) {
                android.app.AlertDialog.Builder(this)
                    .setTitle("اقتراح الإصلاح")
                    .setMessage(result.optString("message"))
                    .setPositiveButton("حسناً", null)
                    .show()
                return
            }
            val fixed = result.optString("fixed_code", source)
            android.app.AlertDialog.Builder(this)
                .setTitle("معاينة الكود المصحح")
                .setMessage(result.optString("message") + "\n\n" + fixed)
                .setPositiveButton("تطبيق") { _, _ -> editor.setText(fixed) }
                .setNeutralButton("نسخ") { _, _ ->
                    val cm = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
                    cm.setPrimaryClip(ClipData.newPlainText("Fixed code", fixed))
                    Toast.makeText(this, "تم نسخ الكود", Toast.LENGTH_SHORT).show()
                }
                .setNegativeButton("إغلاق", null)
                .show()
        } catch (e: Exception) {
            Toast.makeText(this, "تعذر اقتراح الإصلاح: " + e.message, Toast.LENGTH_LONG).show()
        }
    }

    private fun countSeverity(issues: JSONArray, severity: String): Int {
        var count = 0
        for (i in 0 until issues.length()) {
            if (issues.getJSONObject(i).optString("severity") == severity) count++
        }
        return count
    }

    private fun saveHistory(source: String, report: String) {
        try {
            val prefs = getSharedPreferences("code_doctor_history", MODE_PRIVATE)
            val previous = JSONArray(prefs.getString("items", "[]"))
            val next = JSONArray()
            next.put(JSONObject()
                .put("time", System.currentTimeMillis())
                .put("source", source.take(50000))
                .put("report", report.take(20000)))
            for (i in 0 until minOf(previous.length(), 9)) {
                next.put(previous.getJSONObject(i))
            }
            prefs.edit().putString("items", next.toString()).apply()
        } catch (_: Exception) {
            // History is optional; storage failure must not interrupt analysis.
        }
    }

    private fun showHistory() {
        try {
            val items = JSONArray(
                getSharedPreferences("code_doctor_history", MODE_PRIVATE).getString("items", "[]")
            )
            if (items.length() == 0) {
                Toast.makeText(this, "لا يوجد فحص سابق بعد", Toast.LENGTH_SHORT).show()
                return
            }
            val formatter = SimpleDateFormat("dd/MM/yyyy HH:mm", Locale.getDefault())
            val labels = Array(items.length()) { index ->
                val item = items.getJSONObject(index)
                formatter.format(Date(item.optLong("time"))) +
                    " — " + item.optString("report").lineSequence().firstOrNull().orEmpty()
            }
            android.app.AlertDialog.Builder(this)
                .setTitle("سجل آخر 10 فحوصات")
                .setItems(labels) { _, which ->
                    val selected = items.getJSONObject(which)
                    editor.setText(selected.optString("source"))
                    output.text = selected.optString("report")
                    copyButton.isEnabled = true
                    exportButton.isEnabled = true
                }
                .setNegativeButton("إغلاق", null)
                .setNeutralButton("مسح السجل") { _, _ ->
                    android.app.AlertDialog.Builder(this)
                        .setMessage("هل تريد مسح سجل الفحوصات المحفوظ على الهاتف؟")
                        .setPositiveButton("مسح") { _, _ ->
                            getSharedPreferences("code_doctor_history", MODE_PRIVATE)
                                .edit().remove("items").apply()
                            Toast.makeText(this, "تم مسح سجل الفحوصات", Toast.LENGTH_SHORT).show()
                        }
                        .setNegativeButton("إلغاء", null)
                        .show()
                }
                .show()
        } catch (_: Exception) {
            Toast.makeText(this, "تعذر فتح سجل الفحوصات", Toast.LENGTH_SHORT).show()
        }
    }

    private fun wrap() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
    )
}

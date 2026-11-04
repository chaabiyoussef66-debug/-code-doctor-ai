package com.codedoctor.ai

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.chaquo.python.Python
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    private lateinit var editor: EditText
    private lateinit var output: TextView

    private val filePicker = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.data?.let { uri ->
                try {
                    val text = contentResolver.openInputStream(uri)
                        ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }
                    if (text != null) editor.setText(text)
                } catch (e: Exception) {
                    Toast.makeText(this, "تعذرت قراءة الملف: ${e.message}", Toast.LENGTH_LONG).show()
                }
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
            setText("def calculate(a, b):\n    return a / 0\n")
        }
        page.addView(editor, LinearLayout.LayoutParams(-1, 0, 1f).apply {
            topMargin = 8; bottomMargin = 8
        })
        page.addView(Button(this).apply {
            text = "افحص الكود الآن"
            setOnClickListener { analyzeCode() }
        }, wrap())
        output = TextView(this).apply {
            text = "نتائج الفحص ستظهر هنا."
            textSize = 14f
            setTextColor(0xFF17243A.toInt())
            setPadding(10, 14, 10, 14)
        }
        page.addView(ScrollView(this).apply { addView(output) },
            LinearLayout.LayoutParams(-1, 0, 1f).apply { topMargin = 8 })
        page.addView(TextView(this).apply {
            text = "الفحص محلي — لا يتم رفع الكود إلى الإنترنت."
            gravity = Gravity.CENTER
            textSize = 11f
        }, wrap())
        setContentView(ScrollView(this).apply { addView(page) })
    }

    private fun analyzeCode() {
        val source = editor.text.toString()
        if (source.isBlank()) { output.text = "أدخل كوداً أولاً."; return }
        try {
            val raw = Python.getInstance().getModule("analyzer")
                .callAttr("analyze", source).toString()
            val data = JSONObject(raw)
            val issues = data.getJSONArray("issues")
            val report = StringBuilder()
            report.append("حالة الفحص: ").append(data.optString("status"))
                .append("\nعدد الملاحظات: ").append(issues.length()).append("\n\n")
            if (issues.length() == 0) {
                report.append("لم تعثر القواعد الحالية على مشكلة. هذا لا يثبت خلو الكود من الأخطاء.")
            } else {
                for (i in 0 until issues.length()) {
                    val item = issues.getJSONObject(i)
                    report.append("• ").append(item.optString("severity"))
                        .append(" — ").append(item.optString("title"))
                        .append("\nالسطر: ").append(item.optInt("line"))
                        .append("\n").append(item.optString("message"))
                        .append("\nاقتراح: ").append(item.optString("suggestion"))
                        .append("\n\n")
                }
            }
            output.text = report.toString()
        } catch (e: Exception) {
            output.text = "وقع خطأ أثناء التحليل:\n${e.message}"
        }
    }

    private fun wrap() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
    )
}

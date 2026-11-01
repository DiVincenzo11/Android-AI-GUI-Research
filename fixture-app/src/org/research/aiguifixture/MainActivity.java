package org.research.aiguifixture;
import android.app.Activity;
import android.os.Bundle;
import android.widget.*;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import java.util.regex.*;

/** Deterministic GUI fixture. No AI model, network, login, or real user data. */
public class MainActivity extends Activity {
  LinearLayout layout;
  public void onCreate(Bundle b) {
    super.onCreate(b);
    layout = new LinearLayout(this); layout.setOrientation(1); layout.setPadding(24,100,24,24);
    setContentView(layout);
    TextView title = new TextView(this); title.setText("AI GUI Research Fixture\nSIMULATED OUTPUT - NOT AN AI MODEL"); title.setTextSize(22); layout.addView(title);
    Button entry = new Button(this); entry.setId(R.id.entry); entry.setText("AI Assistant"); layout.addView(entry);
    entry.setOnClickListener(v -> showChat());
  }
  void showChat() {
    layout.removeAllViews();
    TextView notice = new TextView(this); notice.setText("AI assistant GUI fixture. Replies are deterministic test data, not AI generation."); notice.setTextSize(20); layout.addView(notice);
    EditText prompt = new EditText(this); prompt.setId(R.id.prompt); prompt.setHint("Test prompt"); prompt.setSingleLine(false); layout.addView(prompt);
    Button send = new Button(this); send.setId(R.id.send); send.setText("Send test prompt"); layout.addView(send);
    TextView answer = new TextView(this); answer.setId(R.id.answer); answer.setTextSize(22); layout.addView(answer);
    send.setOnClickListener(v -> {
      ((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(prompt.getWindowToken(),0);
      Matcher m = Pattern.compile("code ([a-z0-9]+)").matcher(prompt.getText().toString());
      answer.setText(m.find() ? "SIMULATED: 25 code " + m.group(1) : "No test nonce supplied");
    });
  }
}
